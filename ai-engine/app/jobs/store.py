"""In-memory job store.

Suitable for a single-engine deployment. For horizontally scaled deployments
the job state is owned by the Spring Boot orchestration layer (see
docs/ARCHITECTURE.md §7.2) — this store remains the local execution view.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas import AssuranceResult, JobStatus, JobStatusResponse

log = get_logger(__name__)


class JobCancelled(Exception):
    """Raised inside the pipeline when a cooperative cancellation was requested."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobRecord:
    """Mutable state of one analysis run, safe for cross-thread updates."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self.status = JobStatus.QUEUED
        self.progress = 0.0
        self.stage: str | None = None
        self.result: AssuranceResult | None = None
        self.error: str | None = None
        self.submitted_at = _now()
        self.updated_at = self.submitted_at
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    # -- pipeline API -------------------------------------------------------

    def checkpoint(self) -> None:
        """Call between pipeline stages; raises JobCancelled when cancelled."""
        if self._cancel.is_set():
            raise JobCancelled(self.job_id)

    def set_progress(self, progress: float, stage: str | None = None) -> None:
        with self._lock:
            self.progress = float(min(99.0, max(0.0, progress)))
            if stage is not None:
                self.stage = stage
            self.updated_at = _now()

    def mark_running(self) -> None:
        with self._lock:
            self.status = JobStatus.RUNNING
            self.updated_at = _now()

    def complete(self, result: AssuranceResult) -> None:
        with self._lock:
            self.status = JobStatus.COMPLETED
            self.progress = 100.0
            self.result = result
            self.updated_at = _now()

    def fail(self, exc: Exception) -> None:
        with self._lock:
            self.status = JobStatus.CANCELLED if isinstance(exc, JobCancelled) else JobStatus.FAILED
            self.error = str(exc)
            self.updated_at = _now()

    # -- API ----------------------------------------------------------------

    def request_cancel(self) -> bool:
        with self._lock:
            if self.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                self._cancel.set()
                return True
            return False

    def to_response(self) -> JobStatusResponse:
        with self._lock:
            return JobStatusResponse(
                job_id=self.job_id,
                status=self.status,
                progress=self.progress,
                stage=self.stage,
                error=self.error,
                submitted_at=self.submitted_at.isoformat(),
                updated_at=self.updated_at.isoformat(),
                result=self.result,
            )


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create(self) -> JobRecord:
        record = JobRecord(f"tvaj-{uuid.uuid4().hex[:12]}")
        with self._lock:
            self._jobs[record.job_id] = record
        log.info("job %s created", record.job_id)
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def request_cancel(self, job_id: str) -> bool:
        record = self.get(job_id)
        return record.request_cancel() if record else False


_store = JobStore()


def get_job_store() -> JobStore:
    return _store
