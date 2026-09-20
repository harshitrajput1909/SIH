"""Black-box checks: behavioural fingerprinting, reference battery, output
consistency and backdoor probing — the model is treated as an oracle."""

from __future__ import annotations

import hashlib
import json
from collections import Counter

import numpy as np

from app.core.logging import get_logger
from app.schemas import CheckReport, Finding, RiskLevel
from app.services.probes import make_feature_toggles, make_patched

log = get_logger(__name__)


def _findings(findings: list[Finding], prefix: str) -> list[Finding]:
    for i, finding in enumerate(findings):
        finding.finding_id = f"{prefix}-{i + 1:03d}"
    return findings


def _output_digest(output: np.ndarray) -> str:
    rounded = np.round(output.astype(np.float64), 6)
    return hashlib.sha256(rounded.tobytes()).hexdigest()[:16]


def _run(runner, inputs: list[np.ndarray]) -> list[np.ndarray]:
    return [np.asarray(o) for o in runner.run(inputs)]


def _labels(output: np.ndarray) -> np.ndarray | None:
    flat = output.reshape(output.shape[0], -1) if output.ndim >= 2 else output.reshape(1, -1)
    if flat.shape[-1] < 2:
        return None
    return np.argmax(flat, axis=-1)


# ---------------------------------------------------------------------------
# behavioural fingerprinting
# ---------------------------------------------------------------------------


def behavioural_fingerprint(runner, probes, cfg) -> CheckReport:
    outputs_per_probe = [_run(runner, probe) for probe in probes]
    num_outputs = max(len(o) for o in outputs_per_probe)

    per_output = []
    for out_index in range(num_outputs):
        stack = np.stack([probe[out_index].reshape(-1) for probe in outputs_per_probe])
        per_output.append({
            "index": out_index,
            "mean": float(np.mean(stack)),
            "std": float(np.std(stack)),
            "min": float(np.min(stack)),
            "max": float(np.max(stack)),
        })

    digest = hashlib.sha256(json.dumps(per_output, sort_keys=True).encode()).hexdigest()[:16]
    probe_summaries = [
        {
            "probe": i,
            "shapes": [list(o.shape) for o in outputs],
            "digests": [_output_digest(o) for o in outputs],
        }
        for i, outputs in enumerate(outputs_per_probe)
    ]
    metrics = {
        "fingerprint": digest,
        "probe_count": len(probes),
        "per_output": per_output,
        "probes": probe_summaries,
    }
    return CheckReport(check="behavioural_fingerprinting", ran=True, metrics=metrics)


# ---------------------------------------------------------------------------
# reference test battery
# ---------------------------------------------------------------------------


def reference_battery(runner, probes, cfg) -> CheckReport:
    findings: list[Finding] = []
    outputs_per_probe = [_run(runner, probe) for probe in probes]

    nan_probes: list[int] = []
    inf_probes: list[int] = []
    extreme_probes: list[int] = []
    for i, outputs in enumerate(outputs_per_probe):
        for output in outputs:
            values = output.astype(np.float64)
            if np.isnan(values).any():
                nan_probes.append(i)
            if np.isinf(values).any():
                inf_probes.append(i)
            if np.abs(values).max() > 1e8:
                extreme_probes.append(i)
            break  # screen the first output per probe

    # determinism: rerun the first random probe
    rerun_index = 3 if len(probes) > 3 else 0
    first = _run(runner, probes[rerun_index])
    second = _run(runner, probes[rerun_index])
    deterministic = all(
        np.array_equal(a.astype(np.float64), b.astype(np.float64)) for a, b in zip(first, second)
    )

    # constant-output screen: identical digest for >= 80% of probes
    digests = [[_output_digest(o) for o in outputs] for outputs in outputs_per_probe]
    if digests:
        for out_index in range(len(digests[0])):
            counter = Counter(d[out_index] for d in digests)
            top, count = counter.most_common(1)[0]
            if count >= max(3, int(0.8 * len(probes))):
                findings.append(Finding(
                    check="reference_battery",
                    title=f"Output {out_index} is constant across the battery",
                    description=(
                        f"{count} of {len(probes)} probes produced the identical output — "
                        "the model may be dead, saturated or ignoring its input."
                    ),
                    severity=RiskLevel.MEDIUM, confidence=0.9,
                    detail={"output_index": out_index, "matching_probes": count},
                ))

    if nan_probes:
        findings.append(Finding(
            check="reference_battery", title="NaN values in model outputs",
            description=f"Probes {sorted(set(nan_probes))} produced NaN outputs.",
            severity=RiskLevel.HIGH, confidence=1.0, detail={"probes": sorted(set(nan_probes))},
        ))
    if inf_probes:
        findings.append(Finding(
            check="reference_battery", title="Inf values in model outputs",
            description=f"Probes {sorted(set(inf_probes))} produced infinite outputs.",
            severity=RiskLevel.HIGH, confidence=1.0, detail={"probes": sorted(set(inf_probes))},
        ))
    if extreme_probes:
        findings.append(Finding(
            check="reference_battery", title="Exploding outputs under extreme inputs",
            description=f"Probes {sorted(set(extreme_probes))} produced |output| > 1e8.",
            severity=RiskLevel.MEDIUM, confidence=0.9, detail={"probes": sorted(set(extreme_probes))},
        ))
    if not deterministic:
        findings.append(Finding(
            check="reference_battery", title="Non-deterministic behaviour",
            description="The same input produced different outputs on repeated execution.",
            severity=RiskLevel.HIGH, confidence=1.0, detail={},
        ))

    metrics = {
        "probes": len(probes),
        "deterministic": deterministic,
        "nan_probes": sorted(set(nan_probes)),
        "inf_probes": sorted(set(inf_probes)),
        "extreme_probes": sorted(set(extreme_probes)),
    }
    return CheckReport(check="reference_battery", ran=True, findings=_findings(findings, "BAT"), metrics=metrics)


# ---------------------------------------------------------------------------
# output consistency (candidate vs reference)
# ---------------------------------------------------------------------------


def output_consistency(candidate, reference, probes, cfg) -> CheckReport:
    findings: list[Finding] = []
    agreements: list[float] = []
    diffs: list[float] = []

    for i, probe in enumerate(probes):
        cand_outputs = _run(candidate, probe)
        ref_outputs = _run(reference, probe)
        for cand, ref in zip(cand_outputs, ref_outputs):
            c64, r64 = cand.astype(np.float64), ref.astype(np.float64)
            if c64.shape != r64.shape:
                findings.append(Finding(
                    check="output_consistency",
                    title="Output shape mismatch against reference model",
                    description=f"Probe {i}: candidate shape {list(c64.shape)} != reference {list(r64.shape)}.",
                    severity=RiskLevel.HIGH, confidence=1.0,
                    detail={"probe": i, "candidate_shape": list(c64.shape),
                            "reference_shape": list(r64.shape)},
                ))
                return CheckReport(check="output_consistency", ran=True,
                                   findings=_findings(findings, "CON"),
                                   metrics={"agreement_rate": 0.0, "mean_abs_diff": None})

            diffs.append(float(np.mean(np.abs(c64 - r64))))
            cand_labels = _labels(c64)
            ref_labels = _labels(r64)
            if cand_labels is not None:
                agreements.append(float(np.mean(cand_labels == ref_labels)))

    agreement_rate = float(np.mean(agreements)) if agreements else None
    mean_diff = float(np.mean(diffs)) if diffs else 0.0
    divergence = (1.0 - agreement_rate) if agreement_rate is not None else min(1.0, mean_diff)

    if divergence >= cfg.divergence_threshold:
        findings.append(Finding(
            check="output_consistency",
            title="Candidate behaviour diverges from the reference model",
            description=(
                f"Agreement rate {agreement_rate if agreement_rate is not None else 'n/a'} "
                f"(mean abs diff {mean_diff:.4f}) exceeds the divergence threshold "
                f"{cfg.divergence_threshold}."
            ),
            severity=RiskLevel.HIGH if divergence >= 2 * cfg.divergence_threshold else RiskLevel.MEDIUM,
            confidence=0.95,
            detail={"agreement_rate": agreement_rate, "mean_abs_diff": round(mean_diff, 4),
                    "divergence": round(min(1.0, divergence), 3)},
        ))

    metrics = {
        "agreement_rate": agreement_rate,
        "mean_abs_diff": round(mean_diff, 6),
        "divergence": round(min(1.0, divergence), 3),
        "probes": len(probes),
    }
    return CheckReport(check="output_consistency", ran=True, findings=_findings(findings, "CON"), metrics=metrics)


# ---------------------------------------------------------------------------
# backdoor probing
# ---------------------------------------------------------------------------


def backdoor_scan(runner, probes, cfg) -> tuple[CheckReport, dict]:
    """Perturbation-based trigger screen.

    Image-like inputs: spatial patches at the 4 corners + centre.
    Flat inputs: one-feature-at-a-time toggles.
    Every variant is compared against ITS OWN unpatched base run.
    """
    findings: list[Finding] = []
    if not probes:
        return CheckReport(check="backdoor_detection", ran=False, skip_reason="no probes"), {}

    image_like = probes[0][0].ndim >= 3
    variants: list[tuple[str, int, list[np.ndarray]]] = []
    for probe_index, probe in enumerate(probes[:4]):
        if image_like:
            for label, patched in make_patched(probe, value=cfg.patch_value):
                variants.append((label, probe_index, patched))
        else:
            for label, patched in make_feature_toggles(probe, cap=cfg.feature_toggle_cap):
                variants.append((label, probe_index, patched))

    if not variants:
        return (
            CheckReport(check="backdoor_detection", ran=False,
                         skip_reason="input structure supports neither patch nor feature-toggle probes"),
            {},
        )

    base_outputs = {i: _run(runner, probe)[0] for i, probe in enumerate(probes[:4])}

    total_patched = 0
    total_flips = 0
    flip_counter: Counter[str] = Counter()
    for label, probe_index, patched in variants:
        total_patched += 1
        base_out = base_outputs[probe_index]
        patched_out = _run(runner, patched)[0]
        base_labels = _labels(base_out)
        patched_labels = _labels(patched_out)
        if base_labels is not None and patched_labels is not None:
            flip = bool(np.any(base_labels != patched_labels))
        else:
            flip = float(np.abs(patched_out.astype(np.float64)
                                - base_out.astype(np.float64)).mean()) > 0.5
        if flip:
            total_flips += 1
            flip_counter[label] += 1

    flip_rate = total_flips / total_patched if total_patched else 0.0
    concentration = (max(flip_counter.values()) / total_flips) if total_flips else 0.0
    score = round(100.0 * flip_rate * (0.5 + 0.5 * concentration), 1)

    # A perfect trigger only flips the runs at ITS position/feature — so a
    # modest flip rate with high concentration is the meaningful signature.
    concentrated = concentration >= cfg.backdoor_concentration
    if (concentrated and flip_rate >= cfg.backdoor_flip_high) or flip_rate >= 0.4:
        severity = RiskLevel.HIGH
    elif (concentrated and flip_rate >= cfg.backdoor_flip_medium) or flip_rate >= 0.25:
        severity = RiskLevel.MEDIUM
    else:
        severity = RiskLevel.LOW

    if total_flips and flip_rate >= cfg.backdoor_flip_medium and concentration >= cfg.backdoor_concentration:
        top_label = flip_counter.most_common(1)[0][0]
        findings.append(Finding(
            check="backdoor_detection",
            title=f"Trigger-concentrated behavioural flips ({top_label})",
            description=(
                f"{total_flips} of {total_patched} perturbed runs changed the model's output, "
                f"with {concentration:.0%} of flips concentrated on '{top_label}'. "
                "Position/feature-concentrated flips are the black-box signature of a planted trigger."
            ),
            severity=severity,
            confidence=round(min(0.99, 0.5 + flip_rate), 3),
            detail={"flip_rate": round(flip_rate, 3), "concentration": round(concentration, 3),
                    "variants": dict(flip_counter)},
        ))

    metrics = {
        "mode": "patch" if image_like else "feature_toggle",
        "total_patched": total_patched,
        "flips": total_flips,
        "flip_rate": round(flip_rate, 3),
        "concentration": round(concentration, 3),
    }
    risk = {
        "assessed": True,
        "score": score,
        "severity": severity.value,
        "flip_rate": flip_rate,
        "concentration": concentration,
    }
    return CheckReport(check="backdoor_detection", ran=True, findings=_findings(findings, "BKD"), metrics=metrics), risk
