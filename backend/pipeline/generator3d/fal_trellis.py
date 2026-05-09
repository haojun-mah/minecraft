"""Fal Trellis wrapper for converting a single image into a 3D mesh.

The client import is lazy so tests and local environments can still import the
backend without `fal-client` installed. The generated mesh is downloaded to the
job artifact directory as a `.glb` file.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from config import Settings, get_settings

logger = logging.getLogger(__name__)

_DEFAULT_INPUT_PARAMETERS = {
    "ss_guidance_strength": 7.5,
    "ss_sampling_steps": 12,
    "slat_guidance_strength": 3,
    "slat_sampling_steps": 12,
    "mesh_simplify": 0.95,
    "texture_size": 1024,
}

_MIME_TYPE_FALLBACKS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def build_image_data_uri(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(image_path.name)[0] or _MIME_TYPE_FALLBACKS.get(
        image_path.suffix.lower(),
        "image/png",
    )
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


class FalTrellisGenerator3D:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    async def generate(
        self,
        *,
        image: Path,
        output_dir: Path,
        seed: int | None = None,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        response = await asyncio.to_thread(self._submit, image, seed)
        mesh_url, file_name = self._extract_mesh_info(response)
        model_path = output_dir / self._output_file_name(file_name)
        await asyncio.to_thread(self._download_file, mesh_url, model_path)
        return model_path

    def _submit(self, image: Path, seed: int | None) -> Any:
        client = self._get_client()
        arguments: dict[str, Any] = {
            "image_url": build_image_data_uri(image),
            **_DEFAULT_INPUT_PARAMETERS,
        }
        if seed is not None:
            arguments["seed"] = seed
        return client.subscribe("fal-ai/trellis", arguments=arguments)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        self._client = self._create_client()
        return self._client

    def _create_client(self) -> Any:
        if self._settings.fal_key is not None:
            os.environ.setdefault("FAL_KEY", self._settings.fal_key)
        try:
            import fal_client
        except ImportError as exc:  # pragma: no cover - exercised in deployment, not tests
            raise RuntimeError(
                "The fal-client package is required for image-to-3D generation"
            ) from exc
        return fal_client

    def _extract_mesh_info(self, response: Any) -> tuple[str, str | None]:
        payload = self._unwrap_response(response)
        mesh = payload.get("model_mesh")
        if mesh is None:
            raise RuntimeError("Fal Trellis response did not include model_mesh")
        if isinstance(mesh, dict):
            mesh_url = mesh.get("url")
            file_name = mesh.get("file_name")
        else:
            mesh_url = getattr(mesh, "url", None)
            file_name = getattr(mesh, "file_name", None)
        if not mesh_url:
            raise RuntimeError("Fal Trellis response did not include a mesh URL")
        return str(mesh_url), file_name

    def _unwrap_response(self, response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            if "data" in response and isinstance(response["data"], dict):
                return response["data"]
            return response
        data = getattr(response, "data", None)
        if isinstance(data, dict):
            return data
        if data is not None:
            return data.__dict__
        return response.__dict__

    def _output_file_name(self, file_name: str | None) -> str:
        if not file_name:
            return "model.glb"
        suffix = Path(file_name).suffix.lower()
        if suffix in {".glb", ".gltf"}:
            return file_name
        if suffix:
            return f"model{suffix}"
        return "model.glb"

    def _download_file(self, url: str, destination: Path) -> None:
        with urllib.request.urlopen(url) as response:  # pragma: no cover - exercised through integration
            destination.write_bytes(response.read())
