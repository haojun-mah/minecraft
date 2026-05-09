"""Build endpoints: POST /builds, GET /builds/{job_id}."""
from __future__ import annotations

import asyncio
import logging
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from api.schemas import BuildEnqueued, BuildRequest, BuildResult, BuildStatus
from pipeline.runner import run_pipeline
from storage.jobs import JobStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/builds", tags=["builds"])


def _store(request: Request) -> JobStore:
    return request.app.state.job_store


def _artifacts_dir(request: Request) -> Path:
    return request.app.state.artifacts_dir


def _task_set(request: Request) -> set[asyncio.Task[None]]:
    return request.app.state.tasks


@router.post("", response_model=BuildEnqueued, status_code=202)
async def create_build(
    body: BuildRequest,
    store: Annotated[JobStore, Depends(_store)],
    artifacts_dir: Annotated[Path, Depends(_artifacts_dir)],
    tasks: Annotated[set[asyncio.Task[None]], Depends(_task_set)],
) -> BuildEnqueued:
    job_id = "j_" + secrets.token_urlsafe(8)
    store.create(job_id, body)

    task = asyncio.create_task(
        run_pipeline(
            job_id=job_id,
            request=body,
            store=store,
            artifacts_dir=artifacts_dir,
        ),
        name=f"pipeline:{job_id}",
    )
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return BuildEnqueued(job_id=job_id, status="queued")


@router.get("/{job_id}", response_model=BuildStatus | BuildResult)
async def get_build(
    job_id: str,
    store: Annotated[JobStore, Depends(_store)],
) -> BuildStatus | BuildResult:
    record = store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    if record.status == "done" and record.result is not None:
        return record.result
    return BuildStatus(
        job_id=record.job_id,
        status=record.status,
        stage=record.stage,
        progress=record.progress,
        error=record.error,
    )
