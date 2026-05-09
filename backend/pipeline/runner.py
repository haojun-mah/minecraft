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

from api.schemas import BuildRequest
from storage.jobs import JobStore
from storage.sample import build_sample_response

logger = logging.getLogger(__name__)


_TEXT_STAGES_PHASE1: list[tuple[str, float, float]] = [
    ("research", 0.10, 0.4),
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
        stages = _IMAGE_STAGES_PHASE1 if request.input_image_url else _TEXT_STAGES_PHASE1
        store.update_status(job_id, status="running", stage=stages[0][0], progress=0.0)
        await _simulate_pipeline(job_id, store, stages)
        result = build_sample_response(
            job_id=job_id,
            prompt=request.prompt,
            hero_image_url=request.input_image_url if request.input_image_url else None,
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
) -> None:
    """Phase-1 placeholder: walk through the same stages the real pipeline will."""
    for stage, progress, delay_s in stages:
        await asyncio.sleep(delay_s)
        store.update_status(job_id, status="running", stage=stage, progress=progress)
