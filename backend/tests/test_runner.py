"""Integration tests for the combined research -> image -> 3D pipeline."""
from __future__ import annotations

from pathlib import Path

import pytest

import pipeline.runner as pipeline_runner
from api.schemas import BuildRequest
from pipeline.research_types import ReferenceImage, ResearchBundle, VisualDescription
from storage.jobs import JobStore


class FakeRequest:
    def url_for(self, name: str, *, path: str) -> str:
        assert name == "static"
        return f"http://test/static/{path}"


@pytest.mark.asyncio
async def test_text_pipeline_feeds_exa_research_to_openai_and_fal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    job_id = "j_researched"
    request = BuildRequest(
        prompt="a medieval cottage",
        style_hint="blocky low-poly",
        seed=17,
    )
    store = JobStore()
    store.create(job_id, request)
    reference_path = tmp_path / job_id / "refs" / "ref_0.jpg"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(b"reference")
    bundle = ResearchBundle(
        prompt=request.prompt,
        visual_descriptions=[
            VisualDescription(
                description="Architectural visual detail: steep thatched roof"
            ),
            VisualDescription(
                description="Architectural visual detail: dark timber framing"
            ),
        ],
        images=[
            ReferenceImage(
                path=reference_path,
                width=64,
                height=64,
                static_url=f"/static/{job_id}/refs/ref_0.jpg",
                description="Architectural visual detail: pale plaster and stone foundation",
            ),
        ],
    )
    captured: dict[str, object] = {}

    async def fake_research(*args, **kwargs) -> ResearchBundle:
        captured["research_args"] = args
        captured["research_kwargs"] = kwargs
        return bundle

    class FakeOpenAIImageGenerator:
        def __init__(self, *args, **kwargs) -> None:
            captured["openai_init"] = kwargs

        async def generate(
            self,
            *,
            prompt: str,
            output_dir: Path,
            size: str,
            candidate_count: int,
        ) -> Path:
            captured["openai_prompt"] = prompt
            captured["openai_size"] = size
            captured["openai_candidate_count"] = candidate_count
            hero_path = output_dir / "hero.png"
            hero_path.write_bytes(b"hero")
            return hero_path

    async def fake_generate_fal_3d_model(
        *,
        image_path: Path,
        output_dir: Path,
        seed: int | None,
    ) -> Path:
        captured["fal_image_path"] = image_path
        captured["fal_seed"] = seed
        model_path = output_dir / "model.glb"
        model_path.write_bytes(b"model")
        return model_path

    monkeypatch.setattr(pipeline_runner, "research", fake_research)
    monkeypatch.setattr(pipeline_runner, "OpenAIImageGenerator", FakeOpenAIImageGenerator)
    monkeypatch.setattr(pipeline_runner, "_generate_fal_3d_model", fake_generate_fal_3d_model)
    monkeypatch.setattr(
        pipeline_runner,
        "_POST_3D_STAGES_PHASE1",
        [("voxelizing", 0.78, 0), ("block_mapping", 0.90, 0), ("encoding", 0.98, 0)],
    )

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
    assert record.result.hero_image_url == f"http://test/static/{job_id}/hero.png"
    assert captured["research_args"] == (request.prompt,)
    assert captured["fal_image_path"] == tmp_path / job_id / "hero.png"
    assert captured["fal_seed"] == 17

    openai_prompt = str(captured["openai_prompt"])
    assert "Use these Exa research findings as visual references" in openai_prompt
    assert "steep thatched roof" in openai_prompt
    assert "dark timber framing" in openai_prompt
    assert "pale plaster and stone foundation" in openai_prompt
