"""Pydantic schemas: analysis requests and assurance results."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DatasetFormat(str, Enum):
    AUTO = "AUTO"
    COCO = "COCO"
    YOLO = "YOLO"


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


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class DetectorOptions(BaseModel):
    """Optional per-request overrides of engine thresholds (None = default)."""

    image_size: int | None = Field(None, ge=64, le=224)
    folds: int | None = Field(None, ge=2, le=10)
    epochs: int | None = Field(None, ge=1, le=30)
    batch_size: int | None = Field(None, ge=4, le=256)
    near_dup_hamming: int | None = Field(None, ge=0, le=32)
    flood_min_cluster: int | None = Field(None, ge=2)
    flip_pred_prob: float | None = Field(None, ge=0.0, le=1.0)
    flip_confidence_gap: float | None = Field(None, ge=0.0, le=1.0)
    mislabel_min_count: int | None = Field(None, ge=3)
    mislabel_min_rate: float | None = Field(None, ge=0.0, le=1.0)
    mislabel_z: float | None = Field(None, ge=1.0)
    trigger_min_images: int | None = Field(None, ge=2)
    trigger_max_class_share: float | None = Field(None, ge=0.0, le=1.0)
    ood_pct: float | None = Field(None, ge=0.1, le=25.0)
    evidence_limit: int | None = Field(None, ge=1, le=200)
    seed: int | None = None


class AnalysisRequest(BaseModel):
    """Either a server-side directory (or ``.zip``) or an uploaded archive."""

    source_path: str
    dataset_format: DatasetFormat = DatasetFormat.AUTO
    dataset_name: str | None = None
    contributor_manifest: dict[str, str] | None = None
    options: DetectorOptions = Field(default_factory=DetectorOptions)


class JobAccepted(BaseModel):
    job_id: str
    status: JobStatus
    poll_url: str


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    kind: str = "image"                     # image | cluster | pattern | contributor
    image_paths: list[str] = []
    contributor: str | None = None
    detail: dict[str, Any] = {}


class Finding(BaseModel):
    finding_id: str = ""
    detector: str
    title: str
    description: str = ""
    severity: RiskLevel
    confidence: float
    sample_count: int = 0
    contributors: list[str] = []
    evidence: list[EvidenceItem] = []
    detail: dict[str, Any] = {}


class CapabilityReport(BaseModel):
    capability: str
    ran: bool
    skip_reason: str | None = None
    findings: list[Finding] = []


class DatasetSummary(BaseModel):
    name: str
    source_path: str
    format: str
    images_total: int
    images_analysed: int
    images_corrupted: int
    corrupted_samples: list[dict[str, Any]] = []
    missing_labels: int
    class_count: int
    class_names: list[str] = []
    contributor_count: int
    contributors: list[str] = []


class ContributorRiskScore(BaseModel):
    contributor: str
    samples: int
    rates: dict[str, float] = {}
    risk_score: float
    risk_level: RiskLevel
    confidence: float
    flagged: bool


class ComponentScore(BaseModel):
    name: str
    score: float
    weight: float


class AssuranceResult(BaseModel):
    engine_version: str
    dataset: DatasetSummary
    capabilities: list[CapabilityReport]
    contributor_risk_scores: list[ContributorRiskScore]
    component_scores: list[ComponentScore]
    trust_score: float
    risk_level: RiskLevel
    confidence: float
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
    result: AssuranceResult | None = None
