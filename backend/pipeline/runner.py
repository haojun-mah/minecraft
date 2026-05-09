"""Pipeline orchestrator."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import Request

from api.schemas import BuildRequest
from config import get_settings
from pipeline.block_map.apply import apply_semantic_remap, compact_block_grid, save_compacted_grid
from pipeline.block_map.nearest import map_rgb_to_blocks, save_block_grid
from pipeline.block_map.palette import load_block_palette
from pipeline.block_map.semantic import semantic_refine_blocks
from pipeline.generator3d.fal_trellis import FalTrellisGenerator3D
from pipeline.image_gen.openai_image import (
    OpenAIImageGenerator,
    build_hero_prompt,
    choose_hero_image_size,
)
from pipeline.research import research
from pipeline.research_types import ResearchBundle
from pipeline.structure_result import build_result_from_compacted_grid
from pipeline.voxelize import save_voxelized_mesh, voxelize_mesh
from storage.jobs import JobStore

logger = logging.getLogger(__name__)


async def run_pipeline(
    job_id: str,
    build_request: BuildRequest,
    http_request: Request,
    store: JobStore,
    artifacts_dir: Path,
) -> None:
    """Run the build pipeline for a single job.

    On success, writes the final result JSON to the store and marks status=done.
    On failure, marks status=error with the exception message.
    """
    try:
        job_dir = artifacts_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        bundle: ResearchBundle | None = None

        if build_request.input_image_url:
            hero_image_url = build_request.input_image_url
            hero_path = _static_url_to_artifact_path(
                build_request.input_image_url,
                artifacts_dir=artifacts_dir,
            )
        else:
            settings = get_settings()
            store.update_status(job_id, status="running", stage="research", progress=0.05)
            bundle = await research(
                build_request.prompt,
                job_id=job_id,
                artifacts_dir=artifacts_dir,
                settings=settings,
            )
            logger.info(
                "research complete",
                extra={
                    "job_id": job_id,
                    "visual_descriptions": len(bundle.visual_descriptions),
                    "images": len(bundle.images),
                    "cached": bundle.cached,
                },
            )
            store.update_status(job_id, status="running", stage="planning", progress=0.20)
            await asyncio.sleep(0)

            store.update_status(job_id, status="running", stage="image_gen", progress=0.40)
            hero_image_url, hero_path = await _generate_text_hero_image(
                job_id=job_id,
                request=build_request,
                research_bundle=bundle,
                artifacts_dir=artifacts_dir,
                http_request=http_request,
            )

        store.update_status(job_id, status="running", stage="image_to_3d", progress=0.55)
        model_path = await _generate_fal_3d_model(
            image_path=hero_path,
            output_dir=job_dir,
            seed=build_request.seed,
        )

        result = await _run_post_3d_pipeline(
            job_id=job_id,
            build_request=build_request,
            model_path=model_path,
            job_dir=job_dir,
            hero_image_url=hero_image_url,
            research_bundle=bundle,
            store=store,
            settings=get_settings(),
        )
        store.set_result(job_id, result)
    except Exception as exc:  # noqa: BLE001 — top-level pipeline boundary
        logger.exception("pipeline failed", extra={"job_id": job_id})
        store.update_status(
            job_id, status="error", stage="queued", progress=0.0, error=str(exc)
        )


async def _run_post_3d_pipeline(
    *,
    job_id: str,
    build_request: BuildRequest,
    model_path: Path,
    job_dir: Path,
    hero_image_url: str | None,
    research_bundle: ResearchBundle | None,
    store: JobStore,
    settings,
):
    store.update_status(job_id, status="running", stage="voxelizing", progress=0.70)
    logger.info("voxelizing mesh", extra={"job_id": job_id})
    voxels = await asyncio.to_thread(voxelize_mesh, model_path, build_request.max_size)
    logger.info("voxelization done: size=%s filled=%d", voxels.size, int(voxels.filled.sum()), extra={"job_id": job_id})
    save_voxelized_mesh(voxels, job_dir / "voxel_grid.npz")

    store.update_status(job_id, status="running", stage="block_mapping", progress=0.82)
    logger.info("mapping RGB to blocks", extra={"job_id": job_id})
    palette = load_block_palette(settings.block_palette_path)
    stage_a = map_rgb_to_blocks(voxels, palette)
    logger.info("block mapping done: %d unique blocks", len(stage_a.histogram), extra={"job_id": job_id})
    save_block_grid(stage_a, job_dir / "stage_a_blocks.npz")

    logger.info("starting semantic refinement", extra={"job_id": job_id})
    semantic = await semantic_refine_blocks(
        prompt=build_request.prompt,
        style_hint=build_request.style_hint,
        histogram=stage_a.histogram,
        allowed_blocks=palette.block_ids,
        research_bundle=research_bundle,
        output_path=job_dir / "block_refine.json",
        settings=settings,
    )
    logger.info("semantic refinement done: %d remaps", len(semantic.remap), extra={"job_id": job_id})

    logger.info("applying remap and compacting grid", extra={"job_id": job_id})
    final_grid = apply_semantic_remap(stage_a, semantic.remap)
    compacted = compact_block_grid(final_grid)
    save_compacted_grid(compacted, job_dir / "final_blocks.npz")
    logger.info("compacted: palette=%d blocks=%d", len(compacted.palette), int((compacted.indices > 0).sum()), extra={"job_id": job_id})

    store.update_status(job_id, status="running", stage="encoding", progress=0.95)
    logger.info("encoding result", extra={"job_id": job_id})
    await asyncio.sleep(0)
    result = build_result_from_compacted_grid(
        job_id=job_id,
        prompt=build_request.prompt,
        compacted=compacted,
        hero_image_url=hero_image_url,
        input_image_url=build_request.input_image_url,
    )
    logger.info("pipeline complete: %s size=%s", job_id, result.size, extra={"job_id": job_id})
    return result


async def _simulate_pipeline(
    job_id: str,
    store: JobStore,
    stages: list[tuple[str, float, float]],
) -> None:
    """Phase-1 placeholder: walk through the same stages the real pipeline will."""
    for stage, progress, delay_s in stages:
        await asyncio.sleep(delay_s)
        store.update_status(job_id, status="running", stage=stage, progress=progress)


async def _generate_text_hero_image(
    *,
    job_id: str,
    request: BuildRequest,
    research_bundle: ResearchBundle,
    artifacts_dir: Path,
    http_request: Request,
) -> tuple[str, Path]:
    settings = get_settings()
    generator = OpenAIImageGenerator(settings=settings)
    job_dir = artifacts_dir / job_id
    hero_path = await generator.generate(
        prompt=build_hero_prompt(request.prompt, request.style_hint, research_bundle),
        output_dir=job_dir,
        size=choose_hero_image_size(request.max_size),
        candidate_count=settings.openai_image_candidate_count,
    )
    return str(http_request.url_for("static", path=f"{job_id}/{hero_path.name}")), hero_path


async def _generate_fal_3d_model(
    *,
    image_path: Path,
    output_dir: Path,
    seed: int | None,
) -> Path:
    generator = FalTrellisGenerator3D(settings=get_settings())
    return await generator.generate(image=image_path, output_dir=output_dir, seed=seed)


def _static_url_to_artifact_path(url: str, *, artifacts_dir: Path) -> Path:
    parsed_path = unquote(urlparse(url).path)
    prefix = "/static/"
    if not parsed_path.startswith(prefix):
        raise RuntimeError(f"Only local static image URLs are supported: {url}")
    relative_path = parsed_path.removeprefix(prefix)
    image_path = artifacts_dir / relative_path
    if not image_path.exists():
        raise RuntimeError(f"Input image artifact does not exist: {relative_path}")
    return image_path
