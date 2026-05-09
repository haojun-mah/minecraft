"""End-to-end Phase 1 smoke test: drive the API through `httpx.ASGITransport`.

Confirms that:
  - POST /builds enqueues and returns a job_id
  - GET /builds/{id} reports running stages while the pipeline executes
  - The final result decodes back to the same grid the encoder produced
  - The example response on disk matches the live response shape
"""
from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager

from main import app
import pipeline.runner as pipeline_runner
from pipeline.encode import decode_rle_zyx
from storage.sample import SAMPLE_PALETTE, SAMPLE_SIZE, _build_sample_grid
from storage.sample import build_sample_response


_MINIMAL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO8q7RUAAAAASUVORK5CYII="
)


@pytest.mark.asyncio
async def test_full_build_flow(monkeypatch):
    async def _fake_generate_text_hero_image(
        *,
        job_id: str,
        request,
        research_bundle,
        artifacts_dir: Path,
        http_request,
    ) -> tuple[str, Path]:
        hero_path = artifacts_dir / job_id / "hero.png"
        hero_path.parent.mkdir(parents=True, exist_ok=True)
        hero_path.write_bytes(_MINIMAL_PNG)
        return str(http_request.url_for("static", path=f"{job_id}/hero.png")), hero_path

    async def _fake_generate_fal_3d_model(*, image_path: Path, output_dir: Path, seed: int | None) -> Path:
        model_path = output_dir / "model.glb"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"glb")
        return model_path

    async def _fake_run_post_3d_pipeline(**kwargs):
        build_request = kwargs["build_request"]
        return build_sample_response(
            job_id=kwargs["job_id"],
            prompt=build_request.prompt,
            hero_image_url=kwargs["hero_image_url"],
            input_image_url=build_request.input_image_url,
        )

    monkeypatch.setattr(pipeline_runner, "_generate_text_hero_image", _fake_generate_text_hero_image)
    monkeypatch.setattr(pipeline_runner, "_generate_fal_3d_model", _fake_generate_fal_3d_model)
    monkeypatch.setattr(pipeline_runner, "_run_post_3d_pipeline", _fake_run_post_3d_pipeline)

    transport = httpx.ASGITransport(app=app)
    async with LifespanManager(app), httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        h = await client.get("/healthz")
        assert h.status_code == 200

        post = await client.post("/builds", json={"prompt": "a small cottage"})
        assert post.status_code == 202
        job = post.json()
        job_id = job["job_id"]
        assert job["status"] == "queued"

        for _ in range(60):
            await asyncio.sleep(0.5)
            r = await client.get(f"/builds/{job_id}")
            assert r.status_code == 200
            payload = r.json()
            if payload["status"] == "done":
                break
        else:
            pytest.fail("Pipeline did not finish within timeout")

        assert payload["palette"] == SAMPLE_PALETTE
        assert tuple(payload["size"]) == SAMPLE_SIZE
        assert payload["encoding"] == "rle-z-y-x"
        assert payload["input_image_url"] is None
        assert payload["hero_image_url"] is not None

        hero_response = await client.get(payload["hero_image_url"])
        assert hero_response.status_code == 200
        assert hero_response.headers["content-type"] == "image/png"

        model_path = Path(app.state.artifacts_dir) / job_id / "model.glb"
        assert model_path.exists()

        decoded = decode_rle_zyx(payload["blocks"], SAMPLE_SIZE)
        assert decoded == _build_sample_grid()


@pytest.mark.asyncio
async def test_image_build_flow_saves_upload_and_returns_static_url(monkeypatch):
    async def _fake_generate_fal_3d_model(*, image_path: Path, output_dir: Path, seed: int | None) -> Path:
        model_path = output_dir / "model.glb"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(b"glb")
        return model_path

    async def _fake_run_post_3d_pipeline(**kwargs):
        build_request = kwargs["build_request"]
        return build_sample_response(
            job_id=kwargs["job_id"],
            prompt=build_request.prompt,
            hero_image_url=kwargs["hero_image_url"],
            input_image_url=build_request.input_image_url,
        )

    monkeypatch.setattr(pipeline_runner, "_generate_fal_3d_model", _fake_generate_fal_3d_model)
    monkeypatch.setattr(pipeline_runner, "_run_post_3d_pipeline", _fake_run_post_3d_pipeline)

    transport = httpx.ASGITransport(app=app)
    async with LifespanManager(app), httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        post = await client.post(
            "/builds/from-image",
            data={"style_hint": "blocky low-poly"},
            files={"image": ("reference.png", _MINIMAL_PNG, "image/png")},
        )
        assert post.status_code == 202
        job = post.json()
        job_id = job["job_id"]
        assert job["status"] == "queued"

        for _ in range(60):
            await asyncio.sleep(0.5)
            r = await client.get(f"/builds/{job_id}")
            assert r.status_code == 200
            payload = r.json()
            if payload["status"] == "done":
                break
        else:
            pytest.fail("Image pipeline did not finish within timeout")

        assert payload["input_image_url"] is not None
        assert payload["hero_image_url"] == payload["input_image_url"]
        assert payload["prompt"] == "uploaded image: reference"

        image_response = await client.get(payload["input_image_url"])
        assert image_response.status_code == 200
        assert image_response.headers["content-type"] == "image/png"

        model_path = Path(app.state.artifacts_dir) / job_id / "model.glb"
        assert model_path.exists()

        assert payload["palette"] == SAMPLE_PALETTE
        assert tuple(payload["size"]) == SAMPLE_SIZE
        assert payload["encoding"] == "rle-z-y-x"

        decoded = decode_rle_zyx(payload["blocks"], SAMPLE_SIZE)
        assert decoded == _build_sample_grid()


def test_frozen_sample_response_matches_live():
    sample_path = Path(__file__).resolve().parent.parent / "examples" / "sample_response.json"
    data = json.loads(sample_path.read_text())
    assert data["palette"] == SAMPLE_PALETTE
    assert tuple(data["size"]) == SAMPLE_SIZE
    decoded = decode_rle_zyx(data["blocks"], SAMPLE_SIZE)
    assert decoded == _build_sample_grid()
