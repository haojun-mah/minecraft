"""Integration tests for the forced sample-output pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest

import pipeline.runner as pipeline_runner
from api.schemas import BuildRequest
from pipeline.encode import decode_rle_zyx
from storage.jobs import JobStore
from storage.sample import SAMPLE_PALETTE, SAMPLE_SIZE, _build_sample_grid


class FakeRequest:
    def url_for(self, name: str, *, path: str) -> str:
        assert name == "static"
        return f"http://test/static/{path}"


@pytest.mark.asyncio
async def test_pipeline_forces_canonical_sample_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    job_id = "j_forced"
    request = BuildRequest(
        prompt="a medieval cottage",
        style_hint="blocky low-poly",
        seed=17,
    )
    store = JobStore()
    store.create(job_id, request)
    called = False

    async def fail_if_research_runs(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("forced sample output should bypass Exa research")

    monkeypatch.setattr(pipeline_runner, "research", fail_if_research_runs)

    await pipeline_runner.run_pipeline(
        job_id=job_id,
        build_request=request,
        http_request=FakeRequest(),  # type: ignore[arg-type]
        store=store,
        artifacts_dir=tmp_path,
    )

    record = store.get(job_id)
    assert record is not None
    assert record.status == "done"
    assert record.result is not None
    assert called is False
    assert record.result.job_id == job_id
    assert record.result.prompt == request.prompt
    assert record.result.size == SAMPLE_SIZE
    assert record.result.palette == SAMPLE_PALETTE
    assert decode_rle_zyx(record.result.blocks, SAMPLE_SIZE) == _build_sample_grid()
