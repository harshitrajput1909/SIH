"""Trust score & risk level: weighted composite of component health scores."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.schemas import ComponentScore, RiskLevel


@dataclass
class TrustOutcome:
    trust_score: float
    risk_level: RiskLevel
    components: list[ComponentScore]
    confidence: float


def _level(trust: float) -> RiskLevel:
    if trust >= 80:
        return RiskLevel.LOW
    if trust >= 60:
        return RiskLevel.MEDIUM
    if trust >= 40:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def compute_trust(
    samples: list,
    flags: dict[str, np.ndarray],
    consensus,
    cfg,
) -> TrustOutcome:
    n = max(1, len(samples))
    rate = {k: float(v.sum()) / n for k, v in flags.items()}

    integrity = 100.0 * (1.0 - min(1.0, rate["duplicate"] + rate["flood"]))
    labelling = 100.0 * (1.0 - min(1.0, rate["label_flip"] * 1.5 + rate["systematic_mislabel"]))
    security = 100.0 * (1.0 - min(1.0, rate["trigger"] * 5.0))
    distribution = 100.0 * (1.0 - min(1.0, rate["ood"] * 2.0))

    components = [
        ComponentScore(name="integrity", score=round(integrity, 1), weight=cfg.w_integrity),
        ComponentScore(name="labelling", score=round(labelling, 1), weight=cfg.w_labelling),
        ComponentScore(name="security", score=round(security, 1), weight=cfg.w_security),
        ComponentScore(name="distribution", score=round(distribution, 1), weight=cfg.w_distribution),
    ]
    trust = round(
        sum(c.score * c.weight for c in components)
        / sum(c.weight for c in components),
        1,
    )

    # confirmed trigger patches cap the trust regardless of other components:
    # a backdoor vector is disqualifying for training ingestion.
    if flags["trigger"].sum() > 0:
        trust = min(trust, 55.0)

    size_factor = 0.6 + 0.4 * min(1.0, len(samples) / 1000)
    if consensus is not None:
        label_conf, dist_conf = 0.75, 0.70
    else:
        label_conf, dist_conf = 0.40, 0.40
    confidence = round(
        (
            cfg.w_integrity * 0.95
            + cfg.w_labelling * label_conf
            + cfg.w_security * 0.85
            + cfg.w_distribution * dist_conf
        )
        * size_factor,
        3,
    )

    return TrustOutcome(
        trust_score=trust,
        risk_level=_level(trust),
        components=components,
        confidence=confidence,
    )
