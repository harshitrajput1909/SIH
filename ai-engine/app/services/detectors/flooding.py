"""Near-duplicate flooding: a contributor inflating a class with near-identical images."""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np

from app.schemas import EvidenceItem, Finding, RiskLevel


def _majority(values: list[str]) -> tuple[str, float]:
    counter = Counter(values)
    top, count = counter.most_common(1)[0]
    return top, count / len(values)


def _severity(size: int, min_cluster: int) -> RiskLevel:
    if size >= 4 * min_cluster:
        return RiskLevel.CRITICAL
    if size >= 2 * min_cluster:
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


def detect_flooding(
    samples: list,
    clusters: list[list[int]],
    cfg,
) -> tuple[list[Finding], np.ndarray, dict[str, int]]:
    """Returns (findings, per-sample flags, flooded-image count per contributor)."""
    n = len(samples)
    flags = np.zeros(n, dtype=bool)
    contributor_counts: dict[str, int] = defaultdict(int)
    findings: list[Finding] = []

    for cluster in clusters:
        if len(cluster) < cfg.flood_min_cluster:
            continue
        labels = [samples[i].label_name for i in cluster]
        contributors = [samples[i].contributor for i in cluster]
        top_label, label_share = _majority(labels)
        top_contributor, contributor_share = _majority(contributors)
        if label_share < 0.8 or contributor_share < 0.8:
            continue  # not a coherent flood: mixed content / mixed sources

        findings.append(
            Finding(
                detector="near_duplicate_flooding",
                title=f"Near-duplicate flooding ({len(cluster)} images of '{top_label}')",
                description=(
                    f"{len(cluster)} near-identical images of class '{top_label}' submitted "
                    f"by '{top_contributor}' ({contributor_share:.0%} of the cluster). "
                    "Class balance and contributor diversity are compromised."
                ),
                severity=_severity(len(cluster), cfg.flood_min_cluster),
                confidence=round(min(1.0, 0.6 + 0.04 * len(cluster)), 3),
                sample_count=len(cluster),
                contributors=[top_contributor],
                evidence=[
                    EvidenceItem(
                        kind="cluster",
                        image_paths=[samples[i].rel_path for i in cluster[: cfg.evidence_limit]],
                        contributor=top_contributor,
                        detail={
                            "cluster_size": len(cluster),
                            "label": top_label,
                            "label_share": round(label_share, 3),
                            "contributor_share": round(contributor_share, 3),
                        },
                    )
                ],
                detail={
                    "cluster_size": len(cluster),
                    "label": top_label,
                    "contributor": top_contributor,
                },
            )
        )
        flags[cluster] = True
        contributor_counts[top_contributor] += len(cluster)

    return findings, flags, dict(contributor_counts)
