"""Unit tests for the Fal image-to-3D wrapper."""
from __future__ import annotations

from pathlib import Path

import pytest

from config import Settings
from pipeline.generator3d.fal_trellis import FalTrellisGenerator3D, build_image_data_uri


class FakeFalClient:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    def subscribe(self, model: str, arguments: dict[str, object]):
        self.calls.append((model, arguments))
        return self.response


@pytest.mark.asyncio
async def test_fal_trellis_downloads_glb(tmp_path: Path):
    source_image = tmp_path / "input.png"
    source_image.write_bytes(b"image-bytes")

    mesh_source = tmp_path / "mesh.glb"
    mesh_source.write_bytes(b"mesh-bytes")

    fake_client = FakeFalClient(
        {
            "model_mesh": {
                "url": mesh_source.as_uri(),
                "file_name": "mesh.glb",
            }
        }
    )

    generator = FalTrellisGenerator3D(
        settings=Settings(fal_key="test-key"),
        client=fake_client,
    )

    output_path = await generator.generate(
        image=source_image,
        output_dir=tmp_path / "output",
        seed=7,
    )

    assert output_path.name == "mesh.glb"
    assert output_path.read_bytes() == b"mesh-bytes"

    model_name, arguments = fake_client.calls[0]
    assert model_name == "fal-ai/trellis"
    assert arguments["seed"] == 7
    assert arguments["ss_guidance_strength"] == 7.5
    assert arguments["texture_size"] == 1024
    assert arguments["image_url"].startswith("data:image/png;base64,")


def test_build_image_data_uri_uses_file_mime(tmp_path: Path):
    source_image = tmp_path / "input.webp"
    source_image.write_bytes(b"fake-webp-bytes")

    data_uri = build_image_data_uri(source_image)
    assert data_uri.startswith("data:image/webp;base64,")
