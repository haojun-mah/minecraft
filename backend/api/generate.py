"""POST /generate — synchronous wrapper for the Minecraft frontend mod.

Accepts {"prompt": "..."}, waits for the backend job to finish, then returns
a flat [{x, y, z, block}] list the mod can place directly.
"""
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

_POLL_INTERVAL = 0.5
_TIMEOUT = 120.0


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)


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


@router.post("/generate")
async def generate(
    body: GenerateRequest,
    request: Request,
    store: Annotated[JobStore, Depends(_store)],
) -> list[FlatBlock]:
    job_id = "j_" + secrets.token_urlsafe(8)
    build_request = BuildRequest(prompt=body.prompt)

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

    elapsed = 0.0
    while elapsed < _TIMEOUT:
        await asyncio.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL
        record = store.get(job_id)
        if record is None:
            raise HTTPException(status_code=500, detail="Job record missing")
        if record.status == "error":
            raise HTTPException(status_code=500, detail=record.error or "Pipeline failed")
        if record.status == "done" and record.result is not None:
            try:
                blocks = _decode(record.result)
            except ValueError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            logger.info("[generate] job %s done - %d blocks", job_id, len(blocks))
            return blocks

    raise HTTPException(status_code=504, detail="Pipeline timed out after 120 s")
