"""Analysis pipeline: ingestion -> detectors -> contributor risk -> trust score."""

from __future__ import annotations

import random
import shutil
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from app.core.config import Settings
from app.core.errors import AnalysisError
from app.core.logging import get_logger
from app.schemas import (
    AnalysisRequest,
    AssuranceResult,
    CapabilityReport,
    DatasetSummary,
    DetectorOptions,
    EvidenceItem,
    Finding,
)
from app.services import ingestion
from app.services.detectors import (
    contributor_risk,
    duplicates,
    flooding,
    label_flip,
    ood,
    systematic_mislabel,
    trigger_injection,
)
from app.services.embedding import ImageStore, build_consensus
from app.services.trust import compute_trust

log = get_logger(__name__)

CAPABILITIES = [
    {"name": "duplicate_detection", "description": "Exact (SHA-256) and near duplicates (pHash)."},
    {"name": "near_duplicate_flooding", "description": "Class-inflating clusters of near-identical images from one source."},
    {"name": "label_flip_detection", "description": "Consensus model vs provided labels, plus conflicting duplicate labels."},
    {"name": "systematic_mislabelling", "description": "Contributor-conditional confusion patterns (z-test vs background)."},
    {"name": "trigger_injection", "description": "Recurring, position-consistent, class-rare patch patterns (backdoor triggers)."},
    {"name": "ood_detection", "description": "IsolationForest + per-class Mahalanobis distance on consensus embeddings."},
    {"name": "contributor_risk_aggregation", "description": "Weighted per-contributor risk scores across all detectors."},
]

FINDING_PREFIX = {
    "duplicate_detection": "DUP",
    "near_duplicate_flooding": "FLD",
    "label_flip_detection": "FLP",
    "systematic_mislabelling": "MIS",
    "trigger_injection": "TRG",
    "ood_detection": "OOD",
    "contributor_risk_aggregation": "CNB",
}


@dataclass
class EngineOptions:
    image_size: int
    folds: int
    epochs: int
    batch_size: int
    lr: float
    emb_dim: int
    seed: int
    min_class_samples: int
    min_consensus_classes: int
    near_dup_hamming: int
    dup_max_mad: float
    flood_min_cluster: int
    flip_pred_prob: float
    flip_confidence_gap: float
    mislabel_min_count: int
    mislabel_min_rate: float
    mislabel_z: float
    trigger_min_images: int
    trigger_max_class_share: float
    trigger_scan_cap: int
    ood_pct: float
    ood_min_train: int
    ood_min_samples: int
    evidence_limit: int
    max_samples: int
    cache_images_max: int
    min_train_steps: int
    w_integrity: float
    w_labelling: float
    w_security: float
    w_distribution: float


def effective_options(options: DetectorOptions | None, settings: Settings) -> EngineOptions:
    o = options or DetectorOptions()
    return EngineOptions(
        image_size=o.image_size or settings.image_size,
        folds=o.folds or settings.folds,
        epochs=o.epochs or settings.epochs,
        batch_size=o.batch_size or settings.batch_size,
        lr=settings.lr,
        emb_dim=settings.emb_dim,
        seed=o.seed if o.seed is not None else settings.seed,
        min_class_samples=settings.min_class_samples,
        min_consensus_classes=settings.min_consensus_classes,
        near_dup_hamming=o.near_dup_hamming if o.near_dup_hamming is not None else settings.near_dup_hamming,
        dup_max_mad=settings.dup_max_mad,
        flood_min_cluster=o.flood_min_cluster if o.flood_min_cluster is not None else settings.flood_min_cluster,
        flip_pred_prob=o.flip_pred_prob if o.flip_pred_prob is not None else settings.flip_pred_prob,
        flip_confidence_gap=o.flip_confidence_gap
        if o.flip_confidence_gap is not None
        else settings.flip_confidence_gap,
        mislabel_min_count=o.mislabel_min_count if o.mislabel_min_count is not None else settings.mislabel_min_count,
        mislabel_min_rate=o.mislabel_min_rate if o.mislabel_min_rate is not None else settings.mislabel_min_rate,
        mislabel_z=o.mislabel_z if o.mislabel_z is not None else settings.mislabel_z,
        trigger_min_images=o.trigger_min_images if o.trigger_min_images is not None else settings.trigger_min_images,
        trigger_max_class_share=o.trigger_max_class_share
        if o.trigger_max_class_share is not None
        else settings.trigger_max_class_share,
        trigger_scan_cap=settings.trigger_scan_cap,
        ood_pct=o.ood_pct if o.ood_pct is not None else settings.ood_pct,
        ood_min_train=settings.ood_min_train,
        ood_min_samples=settings.ood_min_samples,
        evidence_limit=o.evidence_limit if o.evidence_limit is not None else settings.evidence_limit,
        max_samples=settings.max_samples,
        cache_images_max=settings.cache_images_max,
        min_train_steps=settings.min_train_steps,
        w_integrity=settings.w_integrity,
        w_labelling=settings.w_labelling,
        w_security=settings.w_security,
        w_distribution=settings.w_distribution,
    )


def _renumber(cap: CapabilityReport, prefix: str) -> None:
    for i, finding in enumerate(cap.findings):
        finding.finding_id = f"{prefix}-{i + 1:03d}"


def run_analysis(
    request: AnalysisRequest,
    settings: Settings,
    job=None,
) -> AssuranceResult:
    """Run the full assurance pipeline. ``job`` (JobRecord) is optional and only
    used for progress reporting and cooperative cancellation."""
    import torch

    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    opts = effective_options(request.options, settings)
    torch.set_num_threads(settings.torch_threads)
    random.seed(opts.seed)
    np.random.seed(opts.seed % (2**31))

    progress: Callable[[float, str | None], None] = lambda *_: None
    checkpoint: Callable[[], None] = lambda: None
    if job is not None:
        progress = job.set_progress
        checkpoint = job.checkpoint

    root = Path(request.source_path)
    if not root.exists():
        raise AnalysisError(f"source path does not exist: {root}")

    # ---------------------------------------------------------------- ingest
    progress(3, "ingest")
    if root.is_file() and root.suffix.lower() == ".zip":
        extract_dir = settings.workspace_dir / "extracts" / uuid.uuid4().hex[:12]
        _extract_zip(root, extract_dir)
        root = extract_dir
    fmt = request.dataset_format.value
    ingest = ingestion.ingest_dataset(
        root=root,
        dataset_format=fmt,
        manifest_override=request.contributor_manifest,
        image_size=opts.image_size,
        cache_images_max=opts.cache_images_max,
        max_samples=opts.max_samples,
    )
    samples = ingest.samples
    n = len(samples)
    if n == 0:
        raise AnalysisError("no decodable images found in the dataset")
    progress(15, "ingest")
    checkpoint()

    limitations: list[str] = []
    if ingest.truncated:
        limitations.append(f"dataset truncated to the first {opts.max_samples} images")
    if not ingest.manifest_present:
        limitations.append(
            "no contributor manifest found (contributors.json or request manifest); "
            "all samples attributed to 'unattributed'"
        )
    if ingest.corrupted:
        limitations.append(f"{len(ingest.corrupted)} images were corrupted/unreadable and excluded")

    # ------------------------------------------------------ duplicates/flood
    progress(20, "duplicate-detection")
    store = ImageStore(samples, opts.image_size)
    dup_findings, dup_clusters, dup_flags = duplicates.detect_duplicates(samples, opts, store)
    progress(28, "near-duplicate-flooding")
    flood_findings, flood_flags, flood_by_contributor = flooding.detect_flooding(
        samples, dup_clusters, opts
    )
    checkpoint()

    # ------------------------------------------------------ consensus models
    progress(30, "consensus")
    labels_arr = np.array(
        [s.label_id if s.label_id is not None else -1 for s in samples], dtype=np.int64
    )

    def consensus_progress(stage: str, pct: float) -> None:
        progress(30 + 40 * float(np.clip(pct, 0, 1)), stage)

    consensus = build_consensus(samples, labels_arr, opts, consensus_progress)
    consensus_skip = None
    if consensus is None:
        consensus_skip = (
            "consensus model skipped: dataset has too few labelled classes/samples "
            f"(min {opts.min_class_samples} per class, {opts.min_consensus_classes} classes)"
        )
        limitations.append(consensus_skip)
    checkpoint()

    # ------------------------------------------------------------- detectors
    progress(74, "label-flip-detection")
    flip_findings, flip_flags, suspects = label_flip.detect_label_flips(
        samples, consensus, dup_clusters, opts
    )
    progress(78, "systematic-mislabelling")
    mis_findings, mis_flags = systematic_mislabel.detect_systematic_mislabelling(
        samples, consensus, opts
    )
    progress(84, "ood-detection")
    ood_findings, ood_flags, ood_skip = ood.detect_ood(samples, consensus, opts)
    if ood_skip:
        limitations.append(f"OOD detection skipped: {ood_skip}")
    checkpoint()

    progress(90, "trigger-injection")
    # duplicates/flooding are excluded from the trigger scan (repeated imagery
    # produces trivially recurring patches). OOD samples deliberately stay in:
    # unusual samples are exactly where planted triggers hide.
    exclude = dup_flags | flood_flags
    trig_findings, trig_flags = trigger_injection.detect_trigger_injection(
        samples, store, exclude, suspects, opts
    )

    # ------------------------------------------------------- aggregation
    progress(94, "contributor-risk")
    flags = {
        "duplicate": dup_flags,
        "flood": flood_flags,
        "label_flip": flip_flags,
        "systematic_mislabel": mis_flags,
        "trigger": trig_flags,
        "ood": ood_flags,
    }
    risk_scores = contributor_risk.aggregate_contributor_risk(samples, flags, opts)

    progress(97, "trust-score")
    trust = compute_trust(samples, flags, consensus, opts)

    contributor_findings = [
        Finding(
            detector="contributor_risk_aggregation",
            title=f"Contributor '{risk.contributor}' flagged (risk {risk.risk_score:.0f}/100)",
            description=(
                f"{risk.samples} samples; rates: "
                + ", ".join(f"{k}={v:.0%}" for k, v in risk.rates.items())
            ),
            severity=risk.risk_level,
            confidence=risk.confidence,
            sample_count=risk.samples,
            contributors=[risk.contributor],
            evidence=[
                EvidenceItem(
                    kind="contributor",
                    image_paths=[],
                    contributor=risk.contributor,
                    detail={"rates": risk.rates, "risk_score": risk.risk_score},
                )
            ],
            detail={"risk_score": risk.risk_score, "rates": risk.rates},
        )
        for risk in risk_scores
        if risk.flagged
    ]

    # ------------------------------------------------------------- assemble
    dataset_summary = DatasetSummary(
        name=request.dataset_name or root.name,
        source_path=str(root),
        format=ingest.format_used.upper(),
        images_total=n + len(ingest.corrupted),
        images_analysed=n,
        images_corrupted=len(ingest.corrupted),
        corrupted_samples=ingest.corrupted[: opts.evidence_limit],
        missing_labels=ingest.missing_labels,
        class_count=len(ingest.class_names),
        class_names=[ingest.class_names[k] for k in sorted(ingest.class_names)],
        contributor_count=len(ingest.contributors),
        contributors=ingest.contributors,
    )

    def _cap(cap_name: str, findings: list[Finding], ran: bool, skip: str | None) -> CapabilityReport:
        report = CapabilityReport(capability=cap_name, ran=ran, skip_reason=skip, findings=findings)
        _renumber(report, FINDING_PREFIX[cap_name])
        return report

    capabilities = [
        _cap("duplicate_detection", dup_findings, True, None),
        _cap("near_duplicate_flooding", flood_findings, True, None),
        _cap("label_flip_detection", flip_findings, consensus is not None, consensus_skip),
        _cap("systematic_mislabelling", mis_findings, consensus is not None, consensus_skip),
        _cap("trigger_injection", trig_findings, True, None),
        _cap("ood_detection", ood_findings, ood_skip is None, ood_skip),
        _cap("contributor_risk_aggregation", contributor_findings, True, None),
    ]

    completed_at = datetime.now(timezone.utc)
    result = AssuranceResult(
        engine_version=settings.version,
        dataset=dataset_summary,
        capabilities=capabilities,
        contributor_risk_scores=risk_scores,
        component_scores=trust.components,
        trust_score=trust.trust_score,
        risk_level=trust.risk_level,
        confidence=trust.confidence,
        limitations=limitations,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        duration_seconds=round(time.perf_counter() - t0, 2),
    )
    progress(100, "complete")
    log.info(
        "analysis done in %.1fs: trust=%.1f risk=%s findings=%s",
        result.duration_seconds,
        result.trust_score,
        result.risk_level.value,
        sum(len(c.findings) for c in capabilities),
    )
    return result


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _extract_zip(zip_path: Path, dest: Path) -> None:
    """Safe zip extraction (zip-slip guarded, size/count capped)."""
    MAX_BYTES = 20 * 1024**3
    MAX_FILES = 200_000
    dest_resolved = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            target = (dest / member.filename).resolve()
            if not str(target).startswith(str(dest_resolved)):
                raise AnalysisError(f"unsafe archive entry: {member.filename}")
            total += member.file_size
            if total > MAX_BYTES:
                raise AnalysisError("archive exceeds uncompressed size limit")
            count += 1
            if count > MAX_FILES:
                raise AnalysisError("archive exceeds file count limit")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
