"""Exa-backed research stage for text prompts."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import time
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
from PIL import Image
from pydantic import BaseModel, Field

from pipeline.exa_client import ExaResult, search_with_contents
from pipeline.research_types import ReferenceImage, ResearchBundle, VisualDescription

if TYPE_CHECKING:
    from config import Settings


logger = logging.getLogger(__name__)

_MAX_VISUAL_DESCRIPTIONS = 5
_MAX_IMAGES = 4
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_MAX_IMAGE_EDGE = 1024
_IMAGE_TIMEOUT_S = 10.0
_SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_IMAGE_URL_BLOCKLIST = ("favicon", "tracking", "pixel", "logo")
_CACHE_VERSION = "architectural-v2-full-descriptions"
_ARCHITECTURAL_QUERY_SUFFIX = (
    "architectural visual reference exterior details materials roof walls windows doors "
    "proportions silhouette construction details close-up reference images"
)
_ARCHITECTURAL_SYSTEM_PROMPT = (
    "Find sources that describe or show architectural and pictorial details of the subject. "
    "Prioritize exterior form, silhouette, proportions, roof shape, wall materials, windows, "
    "doors, trim, texture, colors, structural parts, and close-up reference images. Avoid "
    "generic product pages, shopping pages, logos, maps, and unrelated websites."
)
_ARCHITECTURAL_HIGHLIGHT_QUERY = (
    "architectural details, exterior shape, roof, walls, doors, windows, materials, colors, "
    "proportions, silhouette, decorative features"
)


class _CachedImage(BaseModel):
    filename: str
    width: int
    height: int
    description: str


class _CacheEntry(BaseModel):
    prompt: str
    visual_descriptions: list[VisualDescription] = Field(default_factory=list)
    images: list[_CachedImage] = Field(default_factory=list)
    created_at: float


async def research(
    prompt: str,
    *,
    job_id: str,
    artifacts_dir: Path,
    settings: "Settings",
) -> ResearchBundle:
    """Return visual descriptions and downloaded reference images for `prompt`.

    The research stage is deliberately fault-tolerant. It logs failures and
    returns an empty bundle so downstream stages can fall back to text-only or
    prompt-only behavior.
    """
    artifacts_dir = Path(artifacts_dir)
    refs_dir = artifacts_dir / job_id / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = _manifest_path(artifacts_dir, job_id)

    empty = _with_manifest_path(
        ResearchBundle(prompt=prompt, visual_descriptions=[], images=[], cached=False),
        manifest_path,
    )
    api_key = settings.exa_api_key
    if not api_key:
        logger.warning("EXA_API_KEY is not set; returning empty research bundle")
        _write_job_manifest(empty)
        return empty

    cache_key = _cache_key(prompt)
    cached = _load_cache(
        prompt=prompt,
        job_id=job_id,
        artifacts_dir=artifacts_dir,
        cache_key=cache_key,
        ttl_days=settings.exa_cache_ttl_days,
    )
    if cached is not None:
        _write_job_manifest(cached)
        return cached

    try:
        response = await search_with_contents(
            _architectural_query(prompt),
            api_key=api_key,
            num_results=settings.exa_num_results,
            image_links_per_result=settings.exa_image_links_per_result,
            system_prompt=_ARCHITECTURAL_SYSTEM_PROMPT,
            highlight_query=_ARCHITECTURAL_HIGHLIGHT_QUERY,
        )
    except Exception as exc:  # noqa: BLE001 - research must not fail the pipeline
        logger.warning("Exa research failed: %s", exc)
        _write_job_manifest(empty)
        return empty

    descriptions = _extract_visual_descriptions(response.results)
    image_candidates = _collect_image_candidates(response.results)
    if not image_candidates:
        logger.warning("Exa research produced no usable image URLs")
        _write_job_manifest(empty)
        return empty

    images = await _download_reference_images(image_candidates, refs_dir, job_id)
    if not images:
        logger.warning("Exa research produced no downloadable reference images")
        _write_job_manifest(empty)
        return empty

    bundle = _with_manifest_path(
        ResearchBundle(
            prompt=prompt,
            visual_descriptions=descriptions,
            images=images,
            cached=False,
        ),
        manifest_path,
    )
    _write_cache(artifacts_dir=artifacts_dir, cache_key=cache_key, bundle=bundle)
    _write_job_manifest(bundle)
    return bundle


def load_research_bundle(*, artifacts_dir: Path, job_id: str) -> ResearchBundle:
    """Load the fixed per-job research manifest for downstream pipeline stages."""
    path = _manifest_path(Path(artifacts_dir), job_id)
    bundle = ResearchBundle.model_validate_json(path.read_text(encoding="utf-8"))
    return _with_manifest_path(bundle, path)


def _manifest_path(artifacts_dir: Path, job_id: str) -> Path:
    return artifacts_dir / job_id / "research_bundle.json"


def _with_manifest_path(bundle: ResearchBundle, manifest_path: Path) -> ResearchBundle:
    return bundle.model_copy(update={"manifest_path": manifest_path})


def _write_job_manifest(bundle: ResearchBundle) -> None:
    if bundle.manifest_path is None:
        return
    bundle.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    bundle.manifest_path.write_text(
        json.dumps(bundle.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )


def _cache_key(prompt: str) -> str:
    normalized = f"{_CACHE_VERSION}:{prompt.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _architectural_query(prompt: str) -> str:
    cleaned = " ".join(prompt.split())
    return f"{cleaned} {_ARCHITECTURAL_QUERY_SUFFIX}"


def _cache_file(artifacts_dir: Path, cache_key: str) -> Path:
    return artifacts_dir / "_cache" / "exa" / cache_key[:2] / f"{cache_key}.json"


def _cache_image_dir(artifacts_dir: Path, cache_key: str) -> Path:
    return artifacts_dir / "_cache" / "exa" / "img" / cache_key


def _load_cache(
    *,
    prompt: str,
    job_id: str,
    artifacts_dir: Path,
    cache_key: str,
    ttl_days: int,
) -> ResearchBundle | None:
    cache_file = _cache_file(artifacts_dir, cache_key)
    if not cache_file.exists():
        return None

    max_age_s = ttl_days * 24 * 60 * 60
    if max_age_s > 0 and time.time() - cache_file.stat().st_mtime > max_age_s:
        cache_file.unlink(missing_ok=True)
        return None

    try:
        entry = _CacheEntry.model_validate_json(cache_file.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - corrupt cache should self-heal
        logger.warning("Ignoring corrupt Exa cache %s: %s", cache_file, exc)
        cache_file.unlink(missing_ok=True)
        return None

    refs_dir = artifacts_dir / job_id / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    cache_img_dir = _cache_image_dir(artifacts_dir, cache_key)

    images: list[ReferenceImage] = []
    for cached_image in entry.images:
        src = cache_img_dir / cached_image.filename
        if not src.exists():
            logger.warning("Ignoring Exa cache with missing image: %s", src)
            return None
        dst = refs_dir / cached_image.filename
        shutil.copy2(src, dst)
        images.append(
            ReferenceImage(
                path=dst,
                width=cached_image.width,
                height=cached_image.height,
                static_url=f"/static/{job_id}/refs/{cached_image.filename}",
                description=cached_image.description,
            )
        )

    return ResearchBundle(
        prompt=prompt,
        visual_descriptions=entry.visual_descriptions,
        images=images,
        cached=True,
        manifest_path=_manifest_path(artifacts_dir, job_id),
    )


def _write_cache(*, artifacts_dir: Path, cache_key: str, bundle: ResearchBundle) -> None:
    cache_file = _cache_file(artifacts_dir, cache_key)
    cache_img_dir = _cache_image_dir(artifacts_dir, cache_key)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_img_dir.mkdir(parents=True, exist_ok=True)

    cached_images: list[_CachedImage] = []
    for index, image in enumerate(bundle.images):
        filename = f"ref_{index}.jpg"
        shutil.copy2(image.path, cache_img_dir / filename)
        cached_images.append(
            _CachedImage(
                filename=filename,
                width=image.width,
                height=image.height,
                description=image.description,
            )
        )

    entry = _CacheEntry(
        prompt=bundle.prompt,
        visual_descriptions=bundle.visual_descriptions,
        images=cached_images,
        created_at=time.time(),
    )
    cache_file.write_text(
        json.dumps(entry.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )


def _extract_visual_descriptions(results: list[ExaResult]) -> list[VisualDescription]:
    descriptions: list[VisualDescription] = []
    for result in results:
        pieces = [piece.strip() for piece in result.highlights if piece.strip()]
        if not pieces and result.text:
            pieces = [result.text.strip()]
        description = " ".join(pieces)
        if not description:
            continue
        descriptions.append(
            VisualDescription(
                description=_as_visual_description(description),
            )
        )
        if len(descriptions) >= _MAX_VISUAL_DESCRIPTIONS:
            break
    return descriptions


def _as_visual_description(text: str) -> str:
    cleaned = " ".join(text.split())
    return f"Architectural visual detail: {cleaned}"


def _collect_image_candidates(results: list[ExaResult]) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for result in results:
        description = _image_description(result)
        urls = [result.image]
        if result.extras is not None:
            urls.extend(result.extras.image_links)
        for url in urls:
            if not url or not _is_supported_image_url(url):
                continue
            if url in seen:
                continue
            seen.add(url)
            candidates.append((url, description))
    return candidates[:8]


def _image_description(result: ExaResult) -> str:
    pieces = [piece.strip() for piece in result.highlights if piece.strip()]
    if not pieces and result.text:
        pieces = [result.text.strip()]
    if pieces:
        return _as_visual_description(" ".join(pieces))
    if result.title:
        return f"Architectural visual detail image for: {result.title}"
    return "Architectural visual detail image related to the prompt."


def _is_supported_image_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if any(blocked in url.lower() for blocked in _IMAGE_URL_BLOCKLIST):
        return False
    return any(path.endswith(ext) for ext in _SUPPORTED_IMAGE_EXTENSIONS)


async def _download_reference_images(
    candidates: list[tuple[str, str]],
    refs_dir: Path,
    job_id: str,
) -> list[ReferenceImage]:
    refs_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=_IMAGE_TIMEOUT_S, follow_redirects=True) as client:
        tasks = [
            _download_one_image(client, url, title)
            for url, title in candidates
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    images: list[ReferenceImage] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Skipping Exa image download failure: %s", result)
            continue
        if result is None:
            continue
        _source_url, description, image = result
        filename = f"ref_{len(images)}.jpg"
        path = refs_dir / filename
        width, height = _save_resized_jpeg(image, path)
        images.append(
            ReferenceImage(
                path=path,
                width=width,
                height=height,
                static_url=f"/static/{job_id}/refs/{filename}",
                description=description,
            )
        )
        if len(images) >= _MAX_IMAGES:
            break
    return images


async def _download_one_image(
    client: httpx.AsyncClient,
    url: str,
    description: str,
) -> tuple[str, str, Image.Image] | None:
    async with client.stream("GET", url) as response:
        if response.status_code >= 400:
            return None
        content_type = response.headers.get("content-type", "").lower()
        if not content_type.startswith("image/"):
            return None

        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > _MAX_IMAGE_BYTES:
                return None

    image = Image.open(BytesIO(bytes(body)))
    image.load()
    return url, description, image.convert("RGB")


def _save_resized_jpeg(image: Image.Image, path: Path) -> tuple[int, int]:
    width, height = image.size
    longest_edge = max(width, height)
    if longest_edge > _MAX_IMAGE_EDGE:
        scale = _MAX_IMAGE_EDGE / longest_edge
        width = max(1, round(width * scale))
        height = max(1, round(height * scale))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    image.save(path, format="JPEG", quality=85, optimize=True)
    return image.size
