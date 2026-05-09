"""Pipeline orchestrator."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import Request

from api.schemas import BuildRequest
from config import get_settings
from pipeline.generator3d.fal_trellis import FalTrellisGenerator3D
from pipeline.image_gen.openai_image import (
    OpenAIImageGenerator,
    build_hero_prompt,
    choose_hero_image_size,
)
from pipeline.research import research
from pipeline.research_types import ResearchBundle
from storage.jobs import JobStore
from storage.sample import build_sample_response

logger = logging.getLogger(__name__)


_POST_3D_STAGES_PHASE1: list[tuple[str, float, float]] = [
    ("voxelizing", 0.78, 0.4),
    ("block_mapping", 0.90, 0.3),
    ("encoding", 0.98, 0.2),
]


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
        await _generate_fal_3d_model(
            image_path=hero_path,
            output_dir=job_dir,
            seed=build_request.seed,
        )
        await _simulate_pipeline(job_id, store, _POST_3D_STAGES_PHASE1)

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
