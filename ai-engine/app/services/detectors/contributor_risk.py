"""Contributor risk aggregation: fold per-detector flags into one score per contributor."""

from __future__ import annotations

import numpy as np

from app.schemas import ContributorRiskScore, RiskLevel

# capability -> (weight in the risk mix, boost applied to the raw rate)
WEIGHTS = {
    "duplicate": 0.10,
    "flood": 0.20,
    "label_flip": 0.20,
    "systematic_mislabel": 0.15,
    "trigger": 0.30,
    "ood": 0.05,
}
BOOSTS = {
    "duplicate": 1.5,
    "flood": 2.0,
    "label_flip": 2.0,
    "systematic_mislabel": 2.0,
    "trigger": 3.0,
    "ood": 1.0,
}

FLAG_THRESHOLD = 35.0


def _level(score: float) -> RiskLevel:
    if score >= 75:
        return RiskLevel.CRITICAL
    if score >= 50:
        return RiskLevel.HIGH
    if score >= 25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def aggregate_contributor_risk(
    samples: list,
    flags: dict[str, np.ndarray],
    cfg,
) -> list[ContributorRiskScore]:
    """score = 100 * (1 - prod(1 - weight_i * min(1, rate_i * boost_i))).

    A probabilistic-AND mix: one strong signal moves the score, several
    simultaneous signals compound. Rates saturate at 1 after boosting.
    """
    n = len(samples)
    out: list[ContributorRiskScore] = []
    if n == 0:
        return out

    by_contributor: dict[str, list[int]] = {}
    for sample in samples:
        by_contributor.setdefault(sample.contributor, []).append(sample.idx)

    for contributor in sorted(by_contributor):
        idxs = np.array(by_contributor[contributor], dtype=np.int64)
        total = len(idxs)
        rates: dict[str, float] = {}
        survival = 1.0
        for capability, weight in WEIGHTS.items():
            rate = float(flags[capability][idxs].mean()) if total else 0.0
            rates[capability] = round(rate, 4)
            survival *= 1.0 - weight * min(1.0, rate * BOOSTS[capability])
        score = round(100.0 * (1.0 - survival), 1)
        confidence = round(min(1.0, total / 150), 3)
        out.append(
            ContributorRiskScore(
                contributor=contributor,
                samples=total,
                rates=rates,
                risk_score=score,
                risk_level=_level(score),
                confidence=confidence,
                flagged=score >= FLAG_THRESHOLD,
            )
        )

    out.sort(key=lambda r: -r.risk_score)
    return out
