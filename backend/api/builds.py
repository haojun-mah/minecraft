"""Build endpoints: POST /builds, POST /builds/from-image, GET /builds/{job_id}."""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

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


def _start_pipeline(
    *,
    job_id: str,
    body: BuildRequest,
<<<<<<< HEAD
    request: Request,
=======
>>>>>>> origin/frontend
    store: JobStore,
    artifacts_dir: Path,
    tasks: set[asyncio.Task[None]],
) -> None:
    store.create(job_id, body)

    task = asyncio.create_task(
        run_pipeline(
            job_id=job_id,
<<<<<<< HEAD
            build_request=body,
            http_request=request,
=======
            request=body,
>>>>>>> origin/frontend
            store=store,
            artifacts_dir=artifacts_dir,
        ),
        name=f"pipeline:{job_id}",
    )
    tasks.add(task)
    task.add_done_callback(tasks.discard)


def _resolve_prompt(prompt: str | None, image_name: str | None) -> str:
    cleaned = (prompt or "").strip()
    if cleaned:
        return cleaned
    if image_name:
        stem = Path(image_name).stem.replace("_", " ").strip()
        if stem:
            return f"uploaded image: {stem}"
    return "uploaded image"


def _parse_max_size(raw: str | None) -> tuple[int, int, int]:
    if raw is None or raw.strip() == "":
        return (48, 48, 48)
    raw = raw.strip()
    values: list[int]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parts = [part.strip() for part in raw.split(",")]
        values = [int(part) for part in parts if part]
    else:
        if not isinstance(parsed, list):
            raise ValueError("max_size must be a JSON array or comma-separated string")
        values = [int(part) for part in parsed]
    if len(values) != 3:
        raise ValueError("max_size must contain exactly three integers")
    if any(value <= 0 for value in values):
        raise ValueError("max_size values must be positive")
    return (values[0], values[1], values[2])


async def _save_image_upload(
    *,
    job_id: str,
    upload: UploadFile,
    artifacts_dir: Path,
    request: Request,
) -> str:
    job_dir = artifacts_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}:
        suffix = ".png"
    file_name = f"input{suffix}"
    file_path = job_dir / file_name
    file_path.write_bytes(await upload.read())
    return str(request.url_for("static", path=f"{job_id}/{file_name}"))


@router.post("", response_model=BuildEnqueued, status_code=202)
async def create_build(
<<<<<<< HEAD
    request: Request,
=======
>>>>>>> origin/frontend
    body: BuildRequest,
    store: Annotated[JobStore, Depends(_store)],
    artifacts_dir: Annotated[Path, Depends(_artifacts_dir)],
    tasks: Annotated[set[asyncio.Task[None]], Depends(_task_set)],
) -> BuildEnqueued:
    job_id = "j_" + secrets.token_urlsafe(8)
<<<<<<< HEAD
    _start_pipeline(
        job_id=job_id,
        body=body,
        request=request,
        store=store,
        artifacts_dir=artifacts_dir,
        tasks=tasks,
    )
=======
    _start_pipeline(job_id=job_id, body=body, store=store, artifacts_dir=artifacts_dir, tasks=tasks)
>>>>>>> origin/frontend
    return BuildEnqueued(job_id=job_id, status="queued")


@router.post("/from-image", response_model=BuildEnqueued, status_code=202)
async def create_build_from_image(
    request: Request,
    image: Annotated[UploadFile, File(...)],
    store: Annotated[JobStore, Depends(_store)],
    artifacts_dir: Annotated[Path, Depends(_artifacts_dir)],
    tasks: Annotated[set[asyncio.Task[None]], Depends(_task_set)],
    prompt: Annotated[str | None, Form()] = None,
    max_size: Annotated[str | None, Form()] = None,
    style_hint: Annotated[str | None, Form()] = None,
    seed: Annotated[int | None, Form()] = None,
) -> BuildEnqueued:
    job_id = "j_" + secrets.token_urlsafe(8)
    input_image_url = await _save_image_upload(
        job_id=job_id,
        upload=image,
        artifacts_dir=artifacts_dir,
        request=request,
    )
    try:
        parsed_max_size = _parse_max_size(max_size)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    body = BuildRequest(
        prompt=_resolve_prompt(prompt, image.filename),
        max_size=parsed_max_size,
        style_hint=style_hint,
        seed=seed,
        input_image_url=input_image_url,
    )
<<<<<<< HEAD
    _start_pipeline(
        job_id=job_id,
        body=body,
        request=request,
        store=store,
        artifacts_dir=artifacts_dir,
        tasks=tasks,
    )
=======
    _start_pipeline(job_id=job_id, body=body, store=store, artifacts_dir=artifacts_dir, tasks=tasks)
>>>>>>> origin/frontend
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
