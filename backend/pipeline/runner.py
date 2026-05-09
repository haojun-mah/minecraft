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
from collections.abc import Awaitable, Callable

from api.schemas import BuildRequest
from config import get_settings
from pipeline.research import research
from pipeline.image_gen.openai_image import (
    OpenAIImageGenerator,
    build_hero_prompt,
    choose_hero_image_size,
)
from storage.jobs import JobStore
from storage.sample import build_sample_response

logger = logging.getLogger(__name__)


_TEXT_STAGES_AFTER_RESEARCH_PHASE1: list[tuple[str, float, float]] = [
    ("planning", 0.25, 0.4),
    ("image_gen", 0.45, 0.6),
    ("image_to_3d", 0.65, 0.8),
    ("voxelizing", 0.80, 0.4),
    ("block_mapping", 0.90, 0.3),
    ("encoding", 0.98, 0.2),
]

_IMAGE_STAGES_PHASE1: list[tuple[str, float, float]] = [
    ("image_to_3d", 0.55, 0.5),
    ("voxelizing", 0.78, 0.4),
    ("block_mapping", 0.90, 0.3),
    ("encoding", 0.98, 0.2),
]


async def run_pipeline(
    job_id: str,
    request: BuildRequest,
    store: JobStore,
    artifacts_dir: Path,
) -> None:
    """Run the build pipeline for a single job.

    On success, writes the final result JSON to the store and marks status=done.
    On failure, marks status=error with the exception message.
    """
    try:
        if request.input_image_url:
<<<<<<< HEAD
            stages = _IMAGE_STAGES_PHASE1
            store.update_status(job_id, status="running", stage=stages[0][0], progress=0.0)
            await _simulate_pipeline(job_id, store, stages)
        else:
            settings = get_settings()
            store.update_status(job_id, status="running", stage="research", progress=0.05)
            bundle = await research(
                request.prompt,
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
            await _simulate_pipeline(job_id, store, _TEXT_STAGES_AFTER_RESEARCH_PHASE1)

=======
            store.update_status(job_id, status="running", stage="image_to_3d", progress=0.0)
            await _simulate_pipeline(job_id, store, _IMAGE_STAGES_PHASE1)
            hero_image_url = request.input_image_url
        else:
            store.update_status(job_id, status="running", stage="research", progress=0.0)
            hero_image_url = await _simulate_pipeline(
                job_id,
                store,
                _TEXT_STAGES_PHASE1,
                on_image_gen=lambda: _generate_text_hero_image(
                    job_id=job_id,
                    request=request,
                    artifacts_dir=artifacts_dir,
                ),
            )
>>>>>>> refs/remotes/origin/backend
        result = build_sample_response(
            job_id=job_id,
            prompt=request.prompt,
            hero_image_url=hero_image_url,
            input_image_url=request.input_image_url,
        )
        store.set_result(job_id, result)
    except Exception as exc:  # noqa: BLE001 — top-level pipeline boundary
        logger.exception("pipeline failed", extra={"job_id": job_id})
        store.update_status(
            job_id, status="error", stage="queued", progress=0.0, error=str(exc)
        )


async def _simulate_pipeline(
    job_id: str,
    store: JobStore,
    stages: list[tuple[str, float, float]],
    on_image_gen: Callable[[], Awaitable[str]] | None = None,
) -> str | None:
    """Phase-1 placeholder: walk through the same stages the real pipeline will."""
    hero_image_url: str | None = None
    for stage, progress, delay_s in stages:
        await asyncio.sleep(delay_s)
        store.update_status(job_id, status="running", stage=stage, progress=progress)
        if stage == "image_gen" and on_image_gen is not None:
            hero_image_url = await on_image_gen()
    return hero_image_url


async def _generate_text_hero_image(
    *,
    job_id: str,
    request: BuildRequest,
    artifacts_dir: Path,
) -> str:
    settings = get_settings()
    generator = OpenAIImageGenerator(settings=settings)
    job_dir = artifacts_dir / job_id
    hero_path = await generator.generate(
        prompt=build_hero_prompt(request.prompt, request.style_hint),
        output_dir=job_dir,
        size=choose_hero_image_size(request.max_size),
        candidate_count=settings.openai_image_candidate_count,
    )
    return f"/static/{job_id}/{hero_path.name}"
