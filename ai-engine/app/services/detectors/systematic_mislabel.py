"""Systematic mislabelling: one contributor consistently confusing class A -> B."""

from __future__ import annotations

from collections import Counter, defaultdict
import math

import numpy as np

from app.schemas import EvidenceItem, Finding, RiskLevel


def detect_systematic_mislabelling(
    samples: list,
    consensus,
    cfg,
) -> tuple[list[Finding], np.ndarray]:
    """One-proportion z-test per (contributor, true-class -> consensus-class) pair.

    The background rate for a pair excludes the contributor itself, so a single
    poisoning contributor cannot inflate its own baseline.
    """
    n = len(samples)
    flags = np.zeros(n, dtype=bool)
    findings: list[Finding] = []
    if consensus is None:
        return findings, flags

    class_ids = consensus.class_ids
    class_name_of_col = {col: _name_for(samples, class_ids, col) for col in range(len(class_ids))}

    pair_counts: Counter[tuple[str, int, int]] = Counter()
    pair_samples: dict[tuple[str, int, int], list[int]] = defaultdict(list)
    count_ab: Counter[tuple[int, int]] = Counter()
    count_a: Counter[int] = Counter()
    count_contrib_a: Counter[tuple[str, int]] = Counter()
    contrib_samples: Counter[str] = Counter()

    for sample in samples:
        row = consensus.oof_probs[sample.idx]
        if not np.isfinite(row).all() or sample.label_id not in class_ids:
            continue
        a = class_ids.index(sample.label_id)
        b = int(np.argmax(row))
        contrib_samples[sample.contributor] += 1
        count_a[a] += 1
        count_contrib_a[(sample.contributor, a)] += 1
        if a != b:
            count_ab[(a, b)] += 1
            pair_counts[(sample.contributor, a, b)] += 1
            pair_samples[(sample.contributor, a, b)].append(sample.idx)

    for (contributor, a, b), k in pair_counts.items():
        if k < cfg.mislabel_min_count:
            continue
        n_contrib = count_contrib_a[(contributor, a)]
        rate = k / n_contrib if n_contrib else 0.0
        if rate < cfg.mislabel_min_rate:
            continue
        others_ab = count_ab[(a, b)] - k
        others_a = count_a[a] - n_contrib
        p0 = (others_ab + 0.5) / (others_a + 1) if others_a > 0 else 1.0 / len(class_ids)
        variance = n_contrib * p0 * (1 - p0)
        if variance <= 0:
            continue
        z = (k - n_contrib * p0) / math.sqrt(variance)
        if z < cfg.mislabel_z:
            continue

        confidence = round(min(0.99, z / 6), 3)
        severity = RiskLevel.HIGH if z >= cfg.mislabel_z * 1.6 else RiskLevel.MEDIUM
        name_a = class_name_of_col[a]
        name_b = class_name_of_col[b]
        sample_idx = pair_samples[(contributor, a, b)]
        findings.append(
            Finding(
                detector="systematic_mislabelling",
                title=f"Systematic mislabelling by '{contributor}': '{name_a}' -> '{name_b}'",
                description=(
                    f"{k} of {n_contrib} '{name_a}' images from '{contributor}' "
                    f"({rate:.0%}) are consistently recognised as '{name_b}' "
                    f"(background rate {p0:.1%}, z={z:.1f})."
                ),
                severity=severity,
                confidence=confidence,
                sample_count=k,
                contributors=[contributor],
                evidence=[
                    EvidenceItem(
                        kind="image",
                        image_paths=[samples[i].rel_path for i in sample_idx[: cfg.evidence_limit]],
                        contributor=contributor,
                        detail={
                            "true_label": name_a,
                            "consensus_label": name_b,
                            "count": k,
                            "contributor_rate": round(rate, 3),
                            "background_rate": round(p0, 3),
                            "z": round(z, 2),
                        },
                    )
                ],
                detail={
                    "true_label": name_a,
                    "consensus_label": name_b,
                    "count": k,
                    "contributor_total": n_contrib,
                    "rate": round(rate, 3),
                    "background_rate": round(p0, 3),
                    "z": round(z, 2),
                },
            )
        )
        flags[sample_idx] = True

    return findings, flags


def _name_for(samples: list, class_ids: list[int], col: int) -> str:
    label_id = class_ids[col]
    for sample in samples:
        if sample.label_id == label_id:
            return sample.label_name
    return f"class_{label_id}"
