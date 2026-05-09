"""Pipeline orchestrator.

Phase 1: returns a hard-coded sample build after a short simulated delay so
the frontend mod can exercise the full async polling flow before the real
pipeline lands. Later phases will replace `_simulate_pipeline` with the real
research -> plan -> image -> 3D -> voxelize -> map -> encode chain.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

from api.schemas import BuildRequest
from config import get_settings
from fastapi import Request
from pipeline.generator3d.fal_trellis import FalTrellisGenerator3D
from pipeline.image_gen.openai_image import (
    OpenAIImageGenerator,
    build_hero_prompt,
    choose_hero_image_size,
)
from storage.jobs import JobStore
from storage.sample import build_sample_response

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
        if build_request.input_image_url:
            hero_image_url = build_request.input_image_url
            source_image_path = _artifact_path_from_static_url(
                build_request.input_image_url,
                artifacts_dir,
                job_id,
            )
            await _update_stage(store, job_id, "image_to_3d", 0.55, 0.5)
            await _generate_fal_3d_model(
                image_path=source_image_path,
                output_dir=source_image_path.parent,
                seed=build_request.seed,
            )
            await _update_stage(store, job_id, "voxelizing", 0.78, 0.4)
            await _update_stage(store, job_id, "block_mapping", 0.90, 0.3)
            await _update_stage(store, job_id, "encoding", 0.98, 0.2)
        else:
            await _update_stage(store, job_id, "research", 0.10, 0.4)
            await _update_stage(store, job_id, "planning", 0.25, 0.4)
            hero_image_url, hero_image_path = await _generate_text_hero_image(
                job_id=job_id,
                request=build_request,
                http_request=http_request,
                artifacts_dir=artifacts_dir,
            )
            await _update_stage(store, job_id, "image_to_3d", 0.65, 0.0)
            await _generate_fal_3d_model(
                image_path=hero_image_path,
                output_dir=hero_image_path.parent,
                seed=build_request.seed,
            )
            await _update_stage(store, job_id, "voxelizing", 0.80, 0.4)
            await _update_stage(store, job_id, "block_mapping", 0.90, 0.3)
            await _update_stage(store, job_id, "encoding", 0.98, 0.2)

        result = build_sample_response(
            job_id=job_id,
            prompt=build_request.prompt,
            hero_image_url=hero_image_url,
            input_image_url=build_request.input_image_url,
        )
        store.set_result(job_id, result)
    except Exception as exc:  # noqa: BLE001 — top-level pipeline boundary
        logger.exception("pipeline failed", extra={"job_id": job_id})
        store.update_status(
            job_id, status="error", stage="queued", progress=0.0, error=str(exc)
        )


async def _update_stage(
    store: JobStore,
    job_id: str,
    stage: str,
    progress: float,
    delay_s: float,
) -> None:
    await asyncio.sleep(delay_s)
    store.update_status(job_id, status="running", stage=stage, progress=progress)


def _artifact_path_from_static_url(
    static_url: str,
    artifacts_dir: Path,
    job_id: str,
) -> Path:
    file_name = Path(urlparse(static_url).path).name
    return artifacts_dir / job_id / file_name


async def _generate_text_hero_image(
    *,
    job_id: str,
    request: BuildRequest,
    http_request: Request,
    artifacts_dir: Path,
) -> tuple[str, Path]:
    settings = get_settings()
    generator = OpenAIImageGenerator(settings=settings)
    job_dir = artifacts_dir / job_id
    hero_path = await generator.generate(
        prompt=build_hero_prompt(request.prompt, request.style_hint),
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
    settings = get_settings()
    generator = FalTrellisGenerator3D(settings=settings)
    model_path = await generator.generate(
        image=image_path,
        output_dir=output_dir,
        seed=seed,
    )
    logger.info(
        "3d model generated",
        extra={"image_path": str(image_path), "model_path": str(model_path)},
    )
    return model_path
