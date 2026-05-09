"""POST /generate — synchronous wrapper for the Minecraft frontend mod.

Accepts {"prompt": "..."}, waits for the pipeline to finish, then returns
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

logger = logging.getLogger(__name__)
router = APIRouter(tags=["generate"])

_POLL_INTERVAL = 0.5
_TIMEOUT = 120.0


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=500)


def _store(request: Request) -> JobStore:
    return request.app.state.job_store


def _decode(result: BuildResult) -> list[dict]:
    """Decode base64 RLE blocks into [{x, y, z, block}], skipping air."""
    sx, sy, sz = result.size
    ox, oy, oz = result.origin
    palette = result.palette
    raw = base64.b64decode(result.blocks)

    entries = []
    pos = 0
    total = sx * sy * sz

    for i in range(0, len(raw), 2):
        if pos >= total:
            break
        count = raw[i]
        value = raw[i + 1]
        for _ in range(count):
            if pos >= total:
                break
            z = pos // (sx * sy)
            rem = pos % (sx * sy)
            y = rem // sx
            x = rem % sx
            block = palette[value]
            if block != "minecraft:air":
                entries.append({"x": x + ox, "y": y + oy, "z": z + oz, "block": block})
            pos += 1

    return entries


@router.post("/generate")
async def generate(
    body: GenerateRequest,
    request: Request,
    store: Annotated[JobStore, Depends(_store)],
) -> list[dict]:
    job_id = "j_" + secrets.token_urlsafe(8)
    build_req = BuildRequest(prompt=body.prompt)

    store.create(job_id, build_req)
    task = asyncio.create_task(
        run_pipeline(
            job_id=job_id,
            request=build_req,
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
            blocks = _decode(record.result)
            logger.info("[generate] job %s done — %d blocks", job_id, len(blocks))
            return blocks

    raise HTTPException(status_code=504, detail="Pipeline timed out after 120 s")
