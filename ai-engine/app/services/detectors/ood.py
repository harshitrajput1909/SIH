"""Out-of-distribution detection on consensus embeddings.

Combines IsolationForest (global novelty) with per-class Mahalanobis distance
to the nearest class manifold (Ledoit-Wolf shrinkage for stability).
"""

from __future__ import annotations

import numpy as np

from app.schemas import EvidenceItem, Finding, RiskLevel


def _rank01(values: np.ndarray) -> np.ndarray:
    if len(values) <= 1:
        return np.zeros_like(values, dtype=np.float64)
    order = np.argsort(np.argsort(values))
    return order.astype(np.float64) / (len(values) - 1)


def detect_ood(
    samples: list,
    consensus,
    cfg,
) -> tuple[list[Finding], np.ndarray, str | None]:
    """Returns (findings, per-sample flags, skip reason)."""
    n = len(samples)
    flags = np.zeros(n, dtype=bool)
    findings: list[Finding] = []
    if consensus is None:
        return findings, flags, "consensus model unavailable"

    emb = consensus.oof_emb
    valid = np.nonzero(np.isfinite(emb).all(axis=1))[0]
    if len(valid) < cfg.ood_min_train:
        return (
            findings,
            flags,
            f"insufficient covered samples for OOD modelling ({len(valid)} < {cfg.ood_min_train})",
        )

    from sklearn.covariance import LedoitWolf
    from sklearn.ensemble import IsolationForest

    x = emb[valid]
    y = consensus.y

    isolation = IsolationForest(
        n_estimators=150, contamination="auto", random_state=cfg.seed
    ).fit(x)
    s_iso = -isolation.decision_function(x)

    s_mah = np.full(len(valid), np.inf)
    fitted = False
    for col in range(consensus.oof_probs.shape[1]):
        rows = x[y == col]
        if len(rows) < 10:
            continue
        lw = LedoitWolf().fit(rows)
        diff = x - lw.location_
        try:
            inv = np.linalg.inv(lw.covariance_)
            dist = np.sqrt(np.einsum("ij,jk,ik->i", diff, inv, diff))
        except np.linalg.LinAlgError:
            dist = np.linalg.norm(diff, axis=1)
        s_mah = np.minimum(s_mah, dist)
        fitted = True
    if not fitted:
        s_mah = np.zeros(len(valid))

    combined = 0.5 * _rank01(s_iso) + 0.5 * _rank01(s_mah)

    k = max(cfg.ood_min_samples, int(round(cfg.ood_pct / 100 * len(valid))))
    k = min(k, len(valid) // 2)
    if k <= 0:
        return findings, flags, None

    top = valid[np.argsort(-combined)[:k]]
    flags[top] = True
    top_scores = combined[np.argsort(-combined)[:k]]

    by_path = sorted(
        zip(top.tolist(), top_scores.tolist()), key=lambda t: -t[1]
    )
    findings.append(
        Finding(
            detector="ood_detection",
            title=f"Out-of-distribution samples ({k})",
            description=(
                f"{k} samples fall outside the training manifold "
                f"(IsolationForest + per-class Mahalanobis, {consensus.folds}-fold embeddings)."
            ),
            severity=RiskLevel.HIGH if top_scores[0] >= 0.95 else RiskLevel.MEDIUM,
            confidence=round(float(top_scores.mean()), 3),
            sample_count=k,
            contributors=sorted({samples[i].contributor for i in top}),
            evidence=[
                EvidenceItem(
                    kind="image",
                    image_paths=[samples[i].rel_path for i, _ in by_path[: cfg.evidence_limit]],
                    contributor=None,
                    detail={"ood_score": round(float(score), 3)},
                )
                for i, score in by_path[: cfg.evidence_limit]
            ],
            detail={"flagged": k, "covered": int(len(valid)), "max_score": round(float(top_scores[0]), 3)},
        )
    )
    return findings, flags, None
