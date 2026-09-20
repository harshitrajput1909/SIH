"""Pydantic schemas: shift assessment requests and results."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ShiftOptions(BaseModel):
    max_samples_per_side: int | None = Field(None, ge=10, le=100_000)
    psi_bins: int | None = Field(None, ge=4, le=32)
    domain_cv_folds: int | None = Field(None, ge=2, le=10)
    seed: int | None = None


class ShiftRequest(BaseModel):
    """Reference and candidate dataset directories or .zip archives
    (COCO or YOLO layout; labels are used when present)."""

    reference_path: str
    candidate_path: str
    options: ShiftOptions = Field(default_factory=ShiftOptions)


class JobAccepted(BaseModel):
    job_id: str
    status: JobStatus
    poll_url: str


class SideSummary(BaseModel):
    path: str
    images: int
    labelled_images: int
    classes: int
    exif_coverage: float          # fraction of images with any EXIF
    format: str


class EvidenceItem(BaseModel):
    dimension: str
    headline: str
    detail: dict[str, Any] = {}
    image_paths: list[str] = []


class DimensionReport(BaseModel):
    dimension: str                # feature|class|domain|terrain|season|sensor|illumination
    ran: bool
    skip_reason: str | None = None
    score: float = 0.0            # 0-100 drift magnitude
    severity: RiskLevel = RiskLevel.LOW
    statistics: dict[str, Any] = {}


class ShiftAssessmentResult(BaseModel):
    engine_version: str
    reference: SideSummary
    candidate: SideSummary
    dimensions: list[DimensionReport]
    risk_score: float
    risk_level: RiskLevel
    confidence: float
    operational_drift_probability: float
    suspicious_manipulation_probability: float
    disentanglement: dict[str, Any] = {}
    evidence: list[EvidenceItem] = []
    limitations: list[str] = []
    started_at: str
    completed_at: str
    duration_seconds: float


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float
    stage: str | None = None
    error: str | None = None
    submitted_at: str
    updated_at: str
    result: ShiftAssessmentResult | None = None
