"""Assessment pipeline: load → fingerprint → mode checks → capabilities."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from app.core.config import Settings
from app.core.errors import AnalysisError
from app.core.logging import get_logger
from app.schemas import (
    AssessmentMode,
    AssessmentRequest,
    AssessmentOptions,
    BackdoorRisk,
    CheckReport,
    FingerprintDto,
    Finding,
    ModelAssessmentResult,
    ModelFormat,
    ModelInfo,
    RiskLevel,
    SubstitutionVerdict,
)
from app.services import fingerprints as fp
from app.services import probes as probe_utils
from app.services.checks import blackbox, whitebox
from app.services.model_loading import LoadedModel, load_model

log = get_logger(__name__)

CAPABILITIES = [
    {"name": "model_substitution_detection", "description": "Fingerprint and behavioural comparison against a reference artefact."},
    {"name": "backdoor_risk_assessment", "description": "Patch / feature-toggle probes measuring trigger-driven output flips."},
    {"name": "anomalous_behaviour_detection", "description": "Battery anomalies: NaN/Inf, constant, exploding, non-deterministic outputs."},
    {"name": "confidence_score", "description": "Coverage-weighted confidence of the assessment."},
    {"name": "limitation_statement", "description": "Explicit statement of what the assessment could and could not cover."},
]


@dataclass
class EngineOptions:
    probe_count: int
    allow_pickle_execution: bool
    divergence_threshold: float
    seed: int
    patch_value: float
    feature_toggle_cap: int
    backdoor_flip_medium: float
    backdoor_flip_high: float
    backdoor_concentration: float
    extreme_weight_magnitude: float
    max_modules_hooked: int


def effective_options(options: AssessmentOptions | None, settings: Settings) -> EngineOptions:
    o = options or AssessmentOptions()
    return EngineOptions(
        probe_count=o.probe_count or settings.probe_count,
        allow_pickle_execution=(o.allow_pickle_execution if o.allow_pickle_execution is not None
                                else settings.allow_pickle_execution),
        divergence_threshold=(o.divergence_threshold if o.divergence_threshold is not None
                              else settings.divergence_threshold),
        seed=o.seed if o.seed is not None else settings.seed,
        patch_value=1.0,
        feature_toggle_cap=16,
        backdoor_flip_medium=settings.backdoor_flip_medium,
        backdoor_flip_high=settings.backdoor_flip_high,
        backdoor_concentration=settings.backdoor_concentration,
        extreme_weight_magnitude=settings.extreme_weight_magnitude,
        max_modules_hooked=settings.max_modules_hooked,
    )


def _model_info(loaded: LoadedModel) -> ModelInfo:
    return ModelInfo(
        path=str(loaded.path),
        format=loaded.format,
        sha256=loaded.sha256,
        size_bytes=loaded.size_bytes,
        load_ok=loaded.load_ok,
        load_error=loaded.load_error,
        pickle_risk=loaded.pickle_risk,
        input_spec=[{"name": s.name, "shape": s.shape, "dtype": s.dtype} for s in loaded.input_spec],
    )


def run_assessment(request: AssessmentRequest, settings: Settings, job=None) -> ModelAssessmentResult:
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

    model_path = Path(request.model_path)
    if not model_path.exists():
        raise AnalysisError(f"model_path does not exist: {model_path}")
    reference_path = Path(request.reference_model_path) if request.reference_model_path else None
    if request.reference_model_path and not reference_path.exists():
        raise AnalysisError(f"reference_model_path does not exist: {reference_path}")

    limitations: list[str] = []
    checks: list[CheckReport] = []

    # ------------------------------------------------------------- load
    progress(5, "load")
    loaded = load_model(model_path, request.model_format.value, opts.allow_pickle_execution)
    reference: LoadedModel | None = None
    if reference_path is not None:
        reference = load_model(reference_path, request.reference_format.value, opts.allow_pickle_execution)
        if reference.load_error and not reference.load_ok:
            limitations.append(f"reference model could not be loaded: {reference.load_error}")
            reference = None
    if loaded.load_error:
        limitations.append(f"candidate model load issue: {loaded.load_error}")
    checkpoint()

    # ------------------------------------------------------ fingerprints
    progress(15, "fingerprinting")
    candidate_fingerprints: list[FingerprintDto] = [
        fp.file_fingerprint(loaded.path, loaded.sha256),
    ]
    candidate_fingerprints.append(fp.weight_digest(loaded.tensors) or FingerprintDto(
        type="WEIGHT_SHA256", value="unavailable",
        detail={"reason": "no parameters/initializers could be extracted"}))
    arch = fp.architecture_hash(loaded.graph_info)
    if arch:
        candidate_fingerprints.append(arch)

    reference_fingerprints: list[FingerprintDto] = []
    if reference is not None:
        reference_fingerprints.append(fp.file_fingerprint(reference.path, reference.sha256))
        ref_weights = fp.weight_digest(reference.tensors)
        if ref_weights:
            reference_fingerprints.append(ref_weights)
        ref_arch = fp.architecture_hash(reference.graph_info)
        if ref_arch:
            reference_fingerprints.append(ref_arch)
    comparison = fp.compare(candidate_fingerprints, reference_fingerprints) if reference else {}
    checkpoint()

    # ------------------------------------------------------------ probes
    probes: list[list[np.ndarray]] = []
    if loaded.runner is not None and loaded.input_spec:
        probes = probe_utils.make_probes(loaded.input_spec, opts.probe_count, opts.seed)

    # ------------------------------------------------------ white-box
    if request.mode == AssessmentMode.WHITE_BOX:
        progress(30, "parameter-statistics")
        checks.append(whitebox.parameter_statistics(loaded, opts))
        checkpoint()
        progress(45, "layer-analysis")
        checks.append(whitebox.layer_analysis(loaded, reference, opts))
        progress(60, "activation-statistics")
        checks.append(whitebox.activation_statistics(loaded, probes, opts))
    else:
        checks.append(CheckReport(check="parameter_statistics", ran=False,
                                  skip_reason="black-box mode: model internals are not inspected"))
        checks.append(CheckReport(check="layer_analysis", ran=False,
                                  skip_reason="black-box mode: model internals are not inspected"))
        checks.append(CheckReport(check="activation_statistics", ran=False,
                                  skip_reason="black-box mode: model internals are not inspected"))
        limitations.append("black-box mode: parameter statistics, layer analysis and activation "
                           "statistics were not performed")

    # ------------------------------------------------------- black-box
    substitution = SubstitutionVerdict(assessed=False)
    backdoor_risk = BackdoorRisk(assessed=False)
    progress(70, "black-box")
    if loaded.runner is not None and probes:
        checks.append(blackbox.behavioural_fingerprint(loaded.runner, probes, opts))
        progress(78, "reference-battery")
        battery = blackbox.reference_battery(loaded.runner, probes, opts)
        checks.append(battery)
        progress(86, "output-consistency")
        if reference is not None and reference.runner is not None:
            consistency = blackbox.output_consistency(loaded.runner, reference.runner, probes, opts)
            checks.append(consistency)
        else:
            consistency = None
            limitations.append("no executable reference model provided — output consistency "
                               "and full substitution assessment were limited")
        progress(92, "backdoor-scan")
        backdoor_report, risk = blackbox.backdoor_scan(loaded.runner, probes, opts)
        checks.append(backdoor_report)
        backdoor_risk = BackdoorRisk(
            assessed=True,
            score=risk["score"],
            level=RiskLevel[risk["severity"]] if risk["severity"] in RiskLevel.__members__ else RiskLevel.LOW,
            confidence=min(0.99, 0.5 + risk["flip_rate"]) if risk["assessed"] else None,
            detail={k: risk[k] for k in ("flip_rate", "concentration")},
        )
    else:
        checks.append(CheckReport(check="behavioural_fingerprinting", ran=False,
                                  skip_reason=loaded.load_error or "model is not executable in this engine"))
        checks.append(CheckReport(check="reference_battery", ran=False,
                                  skip_reason=loaded.load_error or "model is not executable in this engine"))
        checks.append(CheckReport(check="output_consistency", ran=False,
                                  skip_reason="model is not executable"))
        checks.append(CheckReport(check="backdoor_detection", ran=False,
                                  skip_reason="model is not executable"))
        if loaded.pickle_risk:
            limitations.append(
                "artefact contains pickled objects; execution was refused (allow_pickle_execution=false)")
    checkpoint()

    # ---------------------------------------------- substitution verdict
    if reference is not None:
        comparison = fp.compare(candidate_fingerprints, reference_fingerprints)
        weights_match = comparison.get("WEIGHT_SHA256", {}).get("match", False)
        arch_match = comparison.get("ONNX_GRAPH_HASH", {}).get("match",
                     comparison.get("TORCHSCRIPT_CODE_HASH", {}).get("match", None))
        consistency = next((c for c in checks if c.check == "output_consistency"), None)
        divergence = (consistency.metrics or {}).get("divergence") if consistency and consistency.ran else None

        if weights_match and (arch_match is not False):
            verdict, confidence = "SAME_ARTIFACT", 1.0
        elif divergence is not None and divergence >= opts.divergence_threshold:
            verdict, confidence = "SUBSTITUTION_SUSPECTED", 0.95
        elif weights_match:
            verdict, confidence = "BENIGN_VARIANT", 0.8
        else:
            verdict, confidence = "POSSIBLE_TAMPERING", 0.6
        substitution = SubstitutionVerdict(
            assessed=True, verdict=verdict, confidence=confidence,
            detail={"fingerprints": comparison,
                    "behavioural_divergence": divergence},
        )
        if verdict == "SUBSTITUTION_SUSPECTED":
            limitations.append("model substitution suspected: fingerprints differ from the reference "
                               "and behaviour diverges beyond the accepted threshold")
    else:
        limitations.append("no reference model provided — substitution detection was limited to "
                           "recording fingerprints as the baseline")

    # ------------------------------------------------------ anomalies
    anomalies: list[Finding] = []
    for check in checks:
        if check.check in ("reference_battery", "output_consistency"):
            anomalies.extend(check.findings)

    # ------------------------------------------------------ trust score
    trust = 100.0
    trust -= backdoor_risk.score * 0.5 if backdoor_risk.assessed else 0.0
    trust -= min(40.0, len(anomalies) * 8.0)
    if substitution.verdict == "SUBSTITUTION_SUSPECTED":
        trust = min(trust, 55.0)
    trust = round(max(0.0, trust), 1)
    risk_level = (
        RiskLevel.LOW if trust >= 80 else
        RiskLevel.MEDIUM if trust >= 60 else
        RiskLevel.HIGH if trust >= 40 else
        RiskLevel.CRITICAL
    )

    coverage = 0.4
    if loaded.runner is not None:
        coverage += 0.15
    if any(c.ran and c.check == "parameter_statistics" for c in checks):
        coverage += 0.15
    if reference is not None:
        coverage += 0.15
    if loaded.input_spec:
        coverage += 0.15
    confidence = round(min(1.0, coverage), 3)

    completed_at = datetime.now(timezone.utc)
    progress(100, "complete")
    result = ModelAssessmentResult(
        engine_version=settings.version,
        mode=request.mode,
        format=loaded.format,
        model=_model_info(loaded),
        reference=_model_info(reference) if reference else None,
        fingerprints=candidate_fingerprints,
        checks=checks,
        substitution=substitution,
        backdoor_risk=backdoor_risk,
        anomalies=anomalies,
        trust_score=trust,
        risk_level=risk_level,
        confidence=confidence,
        limitations=limitations,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat(),
        duration_seconds=round(time.perf_counter() - t0, 2),
    )
    log.info(
        "assessment done in %.1fs: mode=%s trust=%.1f risk=%s substitution=%s backdoor=%.0f",
        result.duration_seconds, request.mode.value, trust, risk_level.value,
        substitution.verdict, backdoor_risk.score,
    )
    return result
