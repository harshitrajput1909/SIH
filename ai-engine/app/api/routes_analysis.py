"""Dataset assurance analysis endpoints (async jobs + zip upload)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.core.logging import get_logger
from app.jobs.store import JobCancelled, get_job_store
from app.schemas import (
    AnalysisRequest,
    DetectorOptions,
    JobAccepted,
    JobStatus,
    JobStatusResponse,
)
from app.services.pipeline import CAPABILITIES, run_analysis

router = APIRouter(prefix="/api/v1", tags=["dataset-assurance"])
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# job execution
# ---------------------------------------------------------------------------


def _run_job(job_id: str, request: AnalysisRequest) -> None:
    settings = get_settings()
    store = get_job_store()
    record = store.get(job_id)
    if record is None:  # pragma: no cover - defensive
        return
    record.mark_running()
    log.info("job %s started (source=%s)", job_id, request.source_path)
    try:
        result = run_analysis(request, settings=settings, job=record)
        record.complete(result)
        log.info("job %s completed: trust=%.1f risk=%s", job_id, result.trust_score, result.risk_level.value)
    except JobCancelled:
        record.fail(JobCancelled(job_id))
        log.info("job %s cancelled", job_id)
    except Exception as exc:
        record.fail(exc)
        log.exception("job %s failed: %s", job_id, exc)


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------


@router.post("/analyses", response_model=JobAccepted, status_code=202)
def create_analysis(request: AnalysisRequest, background: BackgroundTasks) -> JobAccepted:
    if not Path(request.source_path).exists():
        raise HTTPException(status_code=422, detail=f"source_path does not exist: {request.source_path}")
    job = get_job_store().create()
    background.add_task(_run_job, job.job_id, request)
    return JobAccepted(job_id=job.job_id, status=job.status, poll_url=f"/api/v1/analyses/{job.job_id}")


@router.post("/analyses/upload", response_model=JobAccepted, status_code=202)
async def upload_analysis(
    background: BackgroundTasks,
    file: UploadFile,
    dataset_format: str = Form("AUTO"),
    dataset_name: str | None = Form(None),
    options_json: str = Form("{}"),
) -> JobAccepted:
    settings = get_settings()
    try:
        options = DetectorOptions(**json.loads(options_json or "{}"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"options_json is not valid JSON: {exc}") from exc
    if file.filename is None or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="upload must be a .zip dataset archive")

    job = get_job_store().create()
    upload_dir = settings.workspace_dir / "uploads" / job.job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    zip_path = upload_dir / "dataset.zip"

    size = 0
    try:
        with zip_path.open("wb") as out:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="upload exceeds size limit")
                out.write(chunk)
    except HTTPException:
        zip_path.unlink(missing_ok=True)
        raise

    request = AnalysisRequest(
        source_path=str(zip_path),
        dataset_format=dataset_format.upper(),  # type: ignore[arg-type]
        dataset_name=dataset_name or Path(file.filename).stem,
        options=options,
    )
    background.add_task(_run_job, job.job_id, request)
    return JobAccepted(job_id=job.job_id, status=job.status, poll_url=f"/api/v1/analyses/{job.job_id}")


@router.get("/analyses/{job_id}", response_model=JobStatusResponse)
def get_analysis(job_id: str) -> JobStatusResponse:
    record = get_job_store().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    return record.to_response()


@router.delete("/analyses/{job_id}")
def cancel_analysis(job_id: str) -> dict:
    record = get_job_store().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown job: {job_id}")
    requested = get_job_store().request_cancel(job_id)
    return {
        "job_id": job_id,
        "cancel_requested": requested,
        "status": JobStatus.CANCELLED.value if not requested else record.status.value,
    }


@router.get("/capabilities")
def capabilities() -> dict:
    return {"count": len(CAPABILITIES), "capabilities": CAPABILITIES}
