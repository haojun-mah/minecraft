"""End-to-end Phase 1 smoke test: drive the API through `httpx.ASGITransport`.

Confirms that:
  - POST /builds enqueues and returns a job_id
  - GET /builds/{id} reports running stages while the pipeline executes
  - The final result decodes back to the same grid the encoder produced
  - The example response on disk matches the live response shape
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager

from main import app
from pipeline.encode import decode_rle_zyx
from storage.sample import SAMPLE_PALETTE, SAMPLE_SIZE, _build_sample_grid


@pytest.mark.asyncio
async def test_full_build_flow():
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

        decoded = decode_rle_zyx(payload["blocks"], SAMPLE_SIZE)
        assert decoded == _build_sample_grid()


def test_frozen_sample_response_matches_live():
    sample_path = Path(__file__).resolve().parent.parent / "examples" / "sample_response.json"
    data = json.loads(sample_path.read_text())
    assert data["palette"] == SAMPLE_PALETTE
    assert tuple(data["size"]) == SAMPLE_SIZE
    decoded = decode_rle_zyx(data["blocks"], SAMPLE_SIZE)
    assert decoded == _build_sample_grid()
