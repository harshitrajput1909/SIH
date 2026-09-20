"""Label flip detection: consensus model vs provided labels.

Two signals:
  1. out-of-fold consensus disagrees confidently with the given label;
  2. duplicate groups whose members carry conflicting labels (strong, model-free
     evidence — identical pixels cannot belong to two classes).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from app.schemas import EvidenceItem, Finding, RiskLevel


def _flip_severity(mean_conf: float) -> RiskLevel:
    if mean_conf >= 0.7:
        return RiskLevel.HIGH
    if mean_conf >= 0.5:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def detect_label_flips(
    samples: list,
    consensus,
    clusters: list[list[int]],
    cfg,
) -> tuple[list[Finding], np.ndarray, list[int]]:
    """Returns (findings, per-sample flags, suspect indices for trigger analysis)."""
    n = len(samples)
    flags = np.zeros(n, dtype=bool)
    findings: list[Finding] = []
    suspects: list[int] = []

    # -- 1. consensus-based flips (out-of-fold) --------------------------------
    if consensus is not None:
        class_ids = consensus.class_ids
        groups: dict[tuple[str, str, str], list[tuple[int, float]]] = defaultdict(list)
        for sample in samples:
            row = consensus.oof_probs[sample.idx]
            if not np.isfinite(row).all() or sample.label_id not in class_ids:
                continue
            col = class_ids.index(sample.label_id)
            pred = int(np.argmax(row))
            if pred == col:
                continue
            p_pred = float(row[pred])
            p_given = float(row[col])
            if p_pred >= cfg.flip_pred_prob and (p_pred - p_given) >= cfg.flip_confidence_gap:
                confidence = round(float(min(0.99, 0.4 + (p_pred - p_given))), 3)
                predicted_name = _name_for(samples, class_ids, pred)
                groups[(sample.contributor, sample.label_name, predicted_name)].append(
                    (sample.idx, confidence)
                )

        for (contributor, given, predicted), members in groups.items():
            members.sort(key=lambda m: -m[1])
            mean_conf = sum(m[1] for m in members) / len(members)
            idxs = [m[0] for m in members]
            findings.append(
                Finding(
                    detector="label_flip_detection",
                    title=f"Label flip: '{given}' consistently read as '{predicted}'",
                    description=(
                        f"{len(members)} images from '{contributor}' labelled '{given}' are "
                        f"consistently recognised as '{predicted}' by the out-of-fold consensus "
                        f"model (mean confidence {mean_conf:.2f})."
                    ),
                    severity=_flip_severity(mean_conf),
                    confidence=round(mean_conf, 3),
                    sample_count=len(members),
                    contributors=[contributor],
                    evidence=[
                        EvidenceItem(
                            kind="image",
                            image_paths=[samples[i].rel_path for i, _ in members[: cfg.evidence_limit]],
                            contributor=contributor,
                            detail={
                                "given_label": given,
                                "consensus_label": predicted,
                                "confidence": conf,
                            },
                        )
                        for i, conf in members[: cfg.evidence_limit]
                    ],
                    detail={
                        "given_label": given,
                        "consensus_label": predicted,
                        "count": len(members),
                    },
                )
            )
            for i, _ in members:
                flags[i] = True
            suspects.extend(idxs)

    # -- 2. conflicting labels inside duplicate groups (model-free) ------------
    for cluster in clusters:
        labelled = {samples[i].label_id: i for i in cluster if samples[i].label_id is not None}
        if len(labelled) < 2:
            continue
        contributors = sorted({samples[i].contributor for i in cluster})
        label_pairs = [
            {"image": samples[i].rel_path, "label": samples[i].label_name}
            for i in cluster[: cfg.evidence_limit]
        ]
        findings.append(
            Finding(
                detector="label_flip_detection",
                title=f"Conflicting labels inside duplicate group ({len(cluster)} images)",
                description=(
                    "Pixel-identical or near-identical images carry different ground-truth "
                    f"labels ({', '.join(samples[i].label_name for i in labelled.values())})."
                ),
                severity=RiskLevel.HIGH,
                confidence=0.95,
                sample_count=len(cluster),
                contributors=contributors,
                evidence=[
                    EvidenceItem(kind="cluster", image_paths=[e["image"] for e in label_pairs],
                                 detail={"labels": label_pairs})
                ],
                detail={"cluster_size": len(cluster), "distinct_labels": len(labelled)},
            )
        )
        flags[cluster] = True
        suspects.extend(cluster)

    return findings, flags, suspects


def _name_for(samples: list, class_ids: list[int], col: int) -> str:
    """Resolve a consensus column back to a readable class name."""
    label_id = class_ids[col]
    for sample in samples:
        if sample.label_id == label_id:
            return sample.label_name
    return f"class_{label_id}"
