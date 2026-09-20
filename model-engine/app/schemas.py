"""Pydantic schemas: assessment requests and results."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AssessmentMode(str, Enum):
    WHITE_BOX = "WHITE_BOX"
    BLACK_BOX = "BLACK_BOX"


class ModelFormat(str, Enum):
    AUTO = "AUTO"
    ONNX = "ONNX"
    PYTORCH = "PYTORCH"
    TORCHSCRIPT = "TORCHSCRIPT"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AssessmentOptions(BaseModel):
    probe_count: int | None = Field(None, ge=4, le=64)
    allow_pickle_execution: bool | None = None
    divergence_threshold: float | None = Field(None, ge=0.0, le=1.0)
    seed: int | None = None


class AssessmentRequest(BaseModel):
    model_path: str
    model_format: ModelFormat = ModelFormat.AUTO
    mode: AssessmentMode = AssessmentMode.WHITE_BOX
    reference_model_path: str | None = None
    reference_format: ModelFormat = ModelFormat.AUTO
    options: AssessmentOptions = Field(default_factory=AssessmentOptions)


class JobAccepted(BaseModel):
    job_id: str
    status: JobStatus
    poll_url: str


class Finding(BaseModel):
    finding_id: str = ""
    check: str
    title: str
    description: str = ""
    severity: RiskLevel = RiskLevel.MEDIUM
    confidence: float = 0.5
    detail: dict[str, Any] = {}


class CheckReport(BaseModel):
    check: str
    ran: bool
    skip_reason: str | None = None
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}


class FingerprintDto(BaseModel):
    type: str
    algorithm: str = "SHA-256"
    value: str
    detail: dict[str, Any] = {}


class ModelInfo(BaseModel):
    path: str
    format: str
    sha256: str | None = None
    size_bytes: int | None = None
    load_ok: bool = False
    load_error: str | None = None
    pickle_risk: bool = False
    input_spec: list[dict[str, Any]] = []


class SubstitutionVerdict(BaseModel):
    assessed: bool = False
    verdict: str | None = None          # SAME_ARTIFACT | BENIGN_VARIANT | POSSIBLE_TAMPERING | SUBSTITUTION_SUSPECTED
    confidence: float | None = None
    detail: dict[str, Any] = {}


class BackdoorRisk(BaseModel):
    assessed: bool = False
    score: float = 0.0
    level: RiskLevel = RiskLevel.LOW
    confidence: float | None = None
    detail: dict[str, Any] = {}


class ModelAssessmentResult(BaseModel):
    engine_version: str
    mode: AssessmentMode
    format: str
    model: ModelInfo
    reference: ModelInfo | None = None
    fingerprints: list[FingerprintDto] = []
    checks: list[CheckReport] = []
    substitution: SubstitutionVerdict = SubstitutionVerdict()
    backdoor_risk: BackdoorRisk = BackdoorRisk()
    anomalies: list[Finding] = []
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
    result: ModelAssessmentResult | None = None
