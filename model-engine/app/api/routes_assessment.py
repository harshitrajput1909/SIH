"""Assessment endpoints (async jobs)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.config import get_settings
from app.core.logging import get_logger
from app.jobs.store import JobCancelled, get_job_store
from app.schemas import (
    AssessmentRequest,
    JobAccepted,
    JobStatusResponse,
)
from app.services.assessment import CAPABILITIES, run_assessment

router = APIRouter(prefix="/api/v1", tags=["model-integrity"])
log = get_logger(__name__)


def _run_job(job_id: str, request: AssessmentRequest) -> None:
    settings = get_settings()
    store = get_job_store()
    record = store.get(job_id)
    if record is None:  # pragma: no cover - defensive
        return
    record.mark_running()
    log.info("job %s started (model=%s mode=%s)", job_id, request.model_path, request.mode.value)
    try:
        result = run_assessment(request, settings=settings, job=record)
        record.complete(result)
        log.info("job %s completed: trust=%.1f substitution=%s", job_id, result.trust_score,
                 result.substitution.verdict)
    except JobCancelled:
        record.fail(JobCancelled(job_id))
        log.info("job %s cancelled", job_id)
    except Exception as exc:
        record.fail(exc)
        log.exception("job %s failed: %s", job_id, exc)


@router.post("/assessments", response_model=JobAccepted, status_code=202)
def create_assessment(request: AssessmentRequest, background: BackgroundTasks) -> JobAccepted:
    from pathlib import Path

    if not Path(request.model_path).exists():
        raise HTTPException(status_code=422, detail=f"model_path does not exist: {request.model_path}")
    if request.reference_model_path and not Path(request.reference_model_path).exists():
        raise HTTPException(status_code=422,
                            detail=f"reference_model_path does not exist: {request.reference_model_path}")
    job = get_job_store().create()
    background.add_task(_run_job, job.job_id, request)
    return JobAccepted(job_id=job.job_id, status=job.status, poll_url=f"/api/v1/assessments/{job.job_id}")


@router.get("/assessments/{job_id}", response_model=JobStatusResponse)
def get_assessment(job_id: str) -> JobStatusResponse:
    record = get_job_store().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    return record.to_response()


@router.delete("/assessments/{job_id}")
def cancel_assessment(job_id: str) -> dict:
    record = get_job_store().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    requested = get_job_store().request_cancel(job_id)
    return {"job_id": job_id, "cancel_requested": requested}


@router.get("/capabilities")
def capabilities() -> dict:
    return {"count": len(CAPABILITIES), "capabilities": CAPABILITIES}
