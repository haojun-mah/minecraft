"""POST /generate — async job start; GET /generate/{job_id} — poll for status/result."""
from __future__ import annotations

import asyncio
import base64
import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.schemas import BuildRequest, BuildResult
from pipeline.runner import run_pipeline
from storage.jobs import JobStore
from storage.sample import FlatBlock

logger = logging.getLogger(__name__)
router = APIRouter(tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)
    max_size: tuple[int, int, int] = (32, 32, 32)


class StartResponse(BaseModel):
    job_id: str


class PollResponse(BaseModel):
    done: bool
    stage: str
    progress: float
    error: str | None = None
    blocks: list[FlatBlock] | None = None


def _store(request: Request) -> JobStore:
    return request.app.state.job_store


def _decode(result: BuildResult) -> list[FlatBlock]:
    """Decode base64 RLE blocks into [{x, y, z, block}], skipping air."""
    if result.encoding != "rle-z-y-x":
        raise ValueError(f"Unsupported block encoding: {result.encoding}")

    sx, sy, sz = result.size
    ox, oy, oz = result.origin
    raw = base64.b64decode(result.blocks)
    if len(raw) % 2 != 0:
        raise ValueError("RLE byte stream length must be even")

    entries: list[FlatBlock] = []
    pos = 0
    total = sx * sy * sz

    for i in range(0, len(raw), 2):
        count = raw[i]
        value = raw[i + 1]
        if value >= len(result.palette):
            raise ValueError(f"Palette index out of range: {value}")
        for _ in range(count):
            if pos >= total:
                break
            z = pos // (sx * sy)
            rem = pos % (sx * sy)
            y = rem // sx
            x = rem % sx
            block = result.palette[value]
            if block != "minecraft:air":
                entries.append({"x": x + ox, "y": y + oy, "z": z + oz, "block": block})
            pos += 1

    return entries


@router.post("/generate", response_model=StartResponse)
async def generate(
    body: GenerateRequest,
    request: Request,
    store: Annotated[JobStore, Depends(_store)],
) -> StartResponse:
    """Start a generation job and return the job_id immediately."""
    job_id = "j_" + secrets.token_urlsafe(8)
    build_request = BuildRequest(prompt=body.prompt, max_size=body.max_size)

    store.create(job_id, build_request)
    task = asyncio.create_task(
        run_pipeline(
            job_id=job_id,
            build_request=build_request,
            http_request=request,
            store=store,
            artifacts_dir=request.app.state.artifacts_dir,
        ),
        name=f"pipeline:{job_id}",
    )
    request.app.state.tasks.add(task)
    task.add_done_callback(request.app.state.tasks.discard)

    logger.info("[generate] started job %s prompt=%r max_size=%s", job_id, body.prompt, body.max_size)
    return StartResponse(job_id=job_id)


@router.get("/generate/{job_id}", response_model=PollResponse)
async def poll_generate(
    job_id: str,
    store: Annotated[JobStore, Depends(_store)],
) -> PollResponse:
    """Poll a generation job. Returns stage+progress while running, blocks when done."""
    record = store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if record.status == "error":
        return PollResponse(done=False, stage="error", progress=0.0, error=record.error)

    if record.status == "done" and record.result is not None:
        try:
            blocks = _decode(record.result)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        logger.info("[poll] job %s done — %d blocks", job_id, len(blocks))
        return PollResponse(done=True, stage="done", progress=1.0, blocks=blocks)

    return PollResponse(
        done=False,
        stage=record.stage or "queued",
        progress=float(record.progress or 0.0),
    )
