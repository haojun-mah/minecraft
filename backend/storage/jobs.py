"""In-memory job store.

Phase 1 keeps everything in-process for simplicity; Phase 5 will swap this
behind the same interface for SQLite-backed persistence.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from api.schemas import (
    BuildRequest,
    BuildResult,
    BuildStatus,
    JobStatus,
    PipelineStage,
)


@dataclass
class JobRecord:
    job_id: str
    request: BuildRequest
    status: JobStatus = "queued"
    stage: PipelineStage = "queued"
    progress: float = 0.0
    error: str | None = None
    result: BuildResult | None = None
    extras: dict[str, str] = field(default_factory=dict)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, request: BuildRequest) -> JobRecord:
        with self._lock:
            record = JobRecord(job_id=job_id, request=request)
            self._jobs[job_id] = record
            return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(
        self,
        job_id: str,
        *,
        status: JobStatus,
        stage: PipelineStage,
        progress: float,
        error: str | None = None,
    ) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return
            record.status = status
            record.stage = stage
            record.progress = max(0.0, min(1.0, progress))
            record.error = error

    def set_result(self, job_id: str, result: BuildResult) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return
            record.status = "done"
            record.stage = "done"
            record.progress = 1.0
            record.result = result

    def status(self, job_id: str) -> BuildStatus | None:
        record = self.get(job_id)
        if record is None:
            return None
        return BuildStatus(
            job_id=record.job_id,
            status=record.status,
            stage=record.stage,
            progress=record.progress,
            error=record.error,
        )
