"""OpenAI-backed hero-image generation.

This module keeps the OpenAI SDK import lazy so the backend can still import
cleanly in environments where the dependency is not installed yet. Tests can
inject fake clients directly.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import Settings, get_settings

logger = logging.getLogger(__name__)

_OUTPUT_MIME_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def build_hero_prompt(prompt: str, style_hint: str | None = None) -> str:
    """Turn the user prompt into an image-to-3D-friendly hero-image prompt."""
    parts: list[str] = []
    cleaned_prompt = prompt.strip()
    if cleaned_prompt:
        parts.append(cleaned_prompt)
    if style_hint:
        cleaned_style = style_hint.strip()
        if cleaned_style:
            parts.append(cleaned_style)
    parts.append(
        "three-quarter view, single isolated subject, plain white background, "
        "even studio lighting, no text, no people, no clutter, photorealistic"
    )
    return ", ".join(parts)


def choose_hero_image_size(max_size: tuple[int, int, int]) -> str:
    """Pick a GPT Image size based on the requested Minecraft bounding box."""
    width = max(max_size[0], max_size[2])
    height = max_size[1]
    if height >= width * 1.2:
        return "1024x1536"
    if width >= height * 1.2:
        return "1536x1024"
    return "1024x1024"


@dataclass(frozen=True)
class GeneratedImage:
    path: Path
    data: bytes
    revised_prompt: str | None = None


class OpenAIImageGenerator:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        ranker_client: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client
        self._ranker_client = ranker_client if ranker_client is not None else client

    async def generate(
        self,
        *,
        prompt: str,
        output_dir: Path,
        size: str,
        candidate_count: int = 1,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        count = max(1, min(int(candidate_count), 10))
        response = await asyncio.to_thread(self._create_images, prompt, size, count)
        candidates = self._extract_candidates(response, output_dir)
        if not candidates:
            raise RuntimeError("OpenAI image generation returned no images")

        best_index = await self._pick_best_candidate(prompt, candidates)
        best_candidate = candidates[best_index]
        hero_path = output_dir / f"hero.{self._settings.openai_image_output_format}"
        hero_path.write_bytes(best_candidate.data)
        return hero_path

    def _create_images(self, prompt: str, size: str, count: int) -> Any:
        client = self._get_client()
        return client.images.generate(
            model=self._settings.openai_image_model,
            prompt=prompt,
            n=count,
            size=size,
            quality=self._settings.openai_image_quality,
            output_format=self._settings.openai_image_output_format,
            background=self._settings.openai_image_background,
            moderation=self._settings.openai_image_moderation,
        )

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        self._client = self._create_client()
        if self._ranker_client is None:
            self._ranker_client = self._client
        return self._client

    def _get_ranker_client(self) -> Any:
        if self._ranker_client is not None:
            return self._ranker_client
        return self._get_client()

    def _create_client(self) -> Any:
        if self._settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is required for hero image generation")
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - exercised in deployment, not tests
            raise RuntimeError(
                "The openai package is required for hero image generation"
            ) from exc
        return OpenAI(api_key=self._settings.openai_api_key)

    def _extract_candidates(self, response: Any, output_dir: Path) -> list[GeneratedImage]:
        items = getattr(response, "data", None) or []
        candidates: list[GeneratedImage] = []
        output_format = self._settings.openai_image_output_format
        for index, item in enumerate(items):
            raw_bytes = self._extract_image_bytes(item)
            candidate_path = output_dir / f"hero_candidate_{index}.{output_format}"
            candidate_path.write_bytes(raw_bytes)
            revised_prompt = getattr(item, "revised_prompt", None)
            candidates.append(
                GeneratedImage(
                    path=candidate_path,
                    data=raw_bytes,
                    revised_prompt=revised_prompt,
                )
            )
        return candidates

    def _extract_image_bytes(self, item: Any) -> bytes:
        b64_json = getattr(item, "b64_json", None)
        if b64_json is None and isinstance(item, dict):
            b64_json = item.get("b64_json")
        if b64_json:
            return base64.b64decode(b64_json)

        url = getattr(item, "url", None)
        if url is None and isinstance(item, dict):
            url = item.get("url")
        if url:
            with urllib.request.urlopen(url) as response:  # pragma: no cover - fallback path
                return response.read()

        raise RuntimeError("OpenAI image response did not include image data")

    async def _pick_best_candidate(self, prompt: str, candidates: list[GeneratedImage]) -> int:
        if len(candidates) == 1:
            return 0
        try:
            return await asyncio.to_thread(self._rank_candidates, prompt, candidates)
        except Exception:  # noqa: BLE001 - ranking is best effort
            logger.exception("image ranking failed; falling back to the first candidate")
            return 0

    def _rank_candidates(self, prompt: str, candidates: list[GeneratedImage]) -> int:
        client = self._get_ranker_client()
        mime_type = _OUTPUT_MIME_TYPES[self._settings.openai_image_output_format]

        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    "Pick the best image for a Minecraft image-to-3D pipeline. "
                    "Prefer a single isolated subject, a plain white background, "
                    "the clearest silhouette, and the least clutter. "
                    "Return only the zero-based index of the best image."
                ),
            },
            {"type": "input_text", "text": f"Original prompt: {prompt}"},
        ]
        for candidate in candidates:
            encoded = base64.b64encode(candidate.data).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{mime_type};base64,{encoded}",
                    "detail": "low",
                }
            )

        response = client.responses.create(
            model=self._settings.openai_image_ranker_model,
            input=[{"role": "user", "content": content}],
        )
        text = getattr(response, "output_text", "") or ""
        if not text and getattr(response, "output", None):
            parts: list[str] = []
            for item in response.output:
                part = getattr(item, "text", None)
                if part:
                    parts.append(str(part))
            text = " ".join(parts)

        match = re.search(r"\b(\d+)\b", text)
        if match is None:
            return 0
        index = int(match.group(1))
        if 0 <= index < len(candidates):
            return index
        return 0
