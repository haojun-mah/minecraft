"""Integration tests for the combined research -> image -> 3D pipeline."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import pipeline.runner as pipeline_runner
from api.schemas import BuildRequest
from pipeline.block_map.nearest import BlockGrid
from pipeline.block_map.palette import BlockPalette
from pipeline.block_map.semantic import SemanticRemap
from pipeline.research_types import ReferenceImage, ResearchBundle, VisualDescription
from pipeline.voxelize import VoxelizedMesh
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

    def fake_voxelize_mesh(model_path: Path, max_size: tuple[int, int, int]) -> VoxelizedMesh:
        captured["voxel_model_path"] = model_path
        captured["voxel_max_size"] = max_size
        filled = np.asarray([[[True]], [[False]]], dtype=bool)
        rgb = np.zeros((2, 1, 1, 3), dtype=np.uint8)
        rgb[0, 0, 0] = [150, 80, 40]
        return VoxelizedMesh(size=(2, 1, 1), filled=filled, rgb=rgb)

    def fake_load_block_palette(path: Path) -> BlockPalette:
        captured["palette_path"] = path
        return BlockPalette(
            block_ids=["minecraft:brown_concrete", "minecraft:oak_planks"],
            rgb=np.asarray([[96, 59, 31], [162, 130, 79]], dtype=np.uint8),
            lab=np.asarray([[30.0, 10.0, 10.0], [55.0, 5.0, 30.0]], dtype=np.float32),
        )

    def fake_map_rgb_to_blocks(voxels: VoxelizedMesh, palette: BlockPalette) -> BlockGrid:
        captured["mapped_voxel_size"] = voxels.size
        blocks = np.asarray([[["minecraft:brown_concrete"]], [["minecraft:air"]]], dtype=object)
        return BlockGrid(
            size=(2, 1, 1),
            blocks=blocks,
            histogram={"minecraft:brown_concrete": 1},
        )

    async def fake_semantic_refine_blocks(**kwargs) -> SemanticRemap:
        captured["semantic_kwargs"] = kwargs
        return SemanticRemap(
            remap={"minecraft:brown_concrete": "minecraft:oak_planks"},
            reasoning_summary="Use planks for cottage wood.",
        )

    monkeypatch.setattr(pipeline_runner, "research", fake_research)
    monkeypatch.setattr(pipeline_runner, "OpenAIImageGenerator", FakeOpenAIImageGenerator)
    monkeypatch.setattr(pipeline_runner, "_generate_fal_3d_model", fake_generate_fal_3d_model)
    monkeypatch.setattr(pipeline_runner, "voxelize_mesh", fake_voxelize_mesh)
    monkeypatch.setattr(pipeline_runner, "load_block_palette", fake_load_block_palette)
    monkeypatch.setattr(pipeline_runner, "map_rgb_to_blocks", fake_map_rgb_to_blocks)
    monkeypatch.setattr(pipeline_runner, "semantic_refine_blocks", fake_semantic_refine_blocks)

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
    assert record.result.size == (2, 1, 1)
    assert record.result.palette == ["minecraft:air", "minecraft:oak_planks"]
    assert captured["research_args"] == (request.prompt,)
    assert captured["fal_image_path"] == tmp_path / job_id / "hero.png"
    assert captured["fal_seed"] == 17
    assert captured["voxel_model_path"] == tmp_path / job_id / "model.glb"
    assert captured["voxel_max_size"] == (48, 48, 48)
    assert captured["semantic_kwargs"]["research_bundle"] is bundle

    openai_prompt = str(captured["openai_prompt"])
    assert "Use these Exa research findings as visual references" in openai_prompt
    assert "steep thatched roof" in openai_prompt
    assert "dark timber framing" in openai_prompt
    assert "pale plaster and stone foundation" in openai_prompt
