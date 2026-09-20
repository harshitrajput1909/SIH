"""Aggregate scoring: risk, confidence, and the operational vs suspicious
disentanglement."""

from __future__ import annotations

import numpy as np

from app.schemas import RiskLevel

# dimension weights in the composite risk score (sum = 1.0)
RISK_WEIGHTS = {
    "domain": 0.30,
    "class": 0.25,
    "feature": 0.20,
    "terrain": 0.0625,
    "season": 0.0625,
    "sensor": 0.0625,
    "illumination": 0.0625,
}


def risk_level(score: float) -> RiskLevel:
    if score >= 75:
        return RiskLevel.CRITICAL
    if score >= 50:
        return RiskLevel.HIGH
    if score >= 25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def composite_risk(dim_scores: dict[str, float]) -> float:
    """Probabilistic-AND blend: one strong dimension moves the score;
    several simultaneous dimensions compound."""
    survival = 1.0
    for dimension, weight in RISK_WEIGHTS.items():
        survival *= 1.0 - weight * min(1.0, dim_scores.get(dimension, 0.0) / 100.0)
    return round(100.0 * (1.0 - survival), 1)


def confidence_score(n_ref: int, n_cand: int, metadata_coverage: float,
                     domain_ran: bool, min_side: int) -> float:
    size_factor = min(1.0, min(n_ref, n_cand) / 300.0)
    coverage_factor = 0.6 + 0.4 * min(1.0, metadata_coverage + 0.25)
    domain_factor = 0.9 if domain_ran else 0.7
    tiny_penalty = 0.6 if min(n_ref, n_cand) < min_side * 2 else 1.0
    return round(float(np.clip(size_factor * coverage_factor * domain_factor * tiny_penalty, 0.05, 1.0)), 3)


def disentangle(
    dim_scores: dict[str, float],
    class_report: dict,
    domain_ran: bool,
    ref_exif_months: list[int],
    cand_exif_months: list[int],
    ref_exif_missing: float,
    cand_exif_missing: float,
    cand_duplicate_rate: float,
    cfg,
) -> dict:
    """Split the observed drift into operational (benign) and suspicious
    (manipulation-consistent) probabilities with a per-signal breakdown."""

    class_tvd = class_report.get("tvd", 0.0)
    context_psis = [dim_scores.get(name, 0.0) for name in ("terrain", "season", "sensor", "illumination")]
    context_psi = float(np.mean(context_psis)) if context_psis else 0.0

    # ----- suspicious signals -------------------------------------------------
    signals: list[dict] = []

    def trigger(name: str, weight: float, strength: float, detail: dict) -> None:
        strength = float(np.clip(strength, 0.0, 1.0))
        signals.append({"signal": name, "weight": weight, "strength": round(strength, 3), "detail": detail})

    # s1: strong class drift while context stays continuous
    if class_tvd > 0:
        continuity = float(np.clip(1.0 - context_psi / 30.0, 0.0, 1.0))
        trigger("class_drift_with_metadata_continuity", 0.30,
                np.clip((class_tvd - cfg.suspicious_class_tvd) / 0.4, 0, 1) * continuity,
                {"class_tvd": round(class_tvd, 3), "context_psi_scaled": round(context_psi, 2)})

    # s2: a few classes capture most of the share movement
    top_jump = class_report.get("max_share_jump", 0.0)
    concentration = class_report.get("concentration", 0.0)
    if top_jump > 0:
        trigger("concentrated_share_jump", 0.25,
                np.clip((top_jump - cfg.suspicious_share_jump) / 0.25, 0, 1) *
                np.clip(concentration / cfg.suspicious_concentration, 0, 1),
                {"max_share_jump": round(top_jump, 3), "concentration": round(concentration, 3)})

    # s3: candidate strips metadata the reference carried
    strip_gap = cand_exif_missing - ref_exif_missing
    if strip_gap > 0:
        trigger("metadata_stripping", 0.20,
                np.clip(strip_gap / cfg.suspicious_exif_strip_gap, 0, 1),
                {"candidate_missing_rate": round(cand_exif_missing, 3),
                 "reference_missing_rate": round(ref_exif_missing, 3)})

    # s4: near-duplicate flooding inside the candidate
    if cand_duplicate_rate > 0:
        trigger("duplicate_flooding", 0.25,
                np.clip(cand_duplicate_rate / cfg.suspicious_dup_rate, 0, 1),
                {"candidate_duplicate_rate": round(cand_duplicate_rate, 3)})

    suspicious = float(np.clip(sum(s["weight"] * s["strength"] for s in signals), 0.0, 1.0))

    # ----- operational signals --------------------------------------------------
    operational_signals: list[dict] = []

    def op_trigger(name: str, weight: float, strength: float, detail: dict) -> None:
        strength = float(np.clip(strength, 0.0, 1.0))
        operational_signals.append({"signal": name, "weight": weight, "strength": round(strength, 3), "detail": detail})

    season_shift = dim_scores.get("season", 0.0)
    months_present = bool(ref_exif_months and cand_exif_months)
    if season_shift > 0:
        op_trigger("season_shift", 0.35,
                   np.clip(season_shift / 40.0, 0, 1) * (1.0 if months_present else 0.6),
                   {"season_score": round(season_shift, 1), "exif_months_available": months_present})

    sensor_shift = dim_scores.get("sensor", 0.0)
    if sensor_shift > 0:
        op_trigger("sensor_change", 0.25, np.clip(sensor_shift / 40.0, 0, 1),
                   {"sensor_score": round(sensor_shift, 1)})

    illumination_shift = dim_scores.get("illumination", 0.0)
    if illumination_shift > 0:
        op_trigger("illumination_change", 0.20, np.clip(illumination_shift / 40.0, 0, 1),
                   {"illumination_score": round(illumination_shift, 1)})

    terrain_shift = dim_scores.get("terrain", 0.0)
    if terrain_shift > 0 and class_tvd < cfg.suspicious_class_tvd:
        op_trigger("terrain_change_with_stable_classes", 0.20,
                   np.clip(terrain_shift / 40.0, 0, 1),
                   {"terrain_score": round(terrain_shift, 1), "class_tvd": round(class_tvd, 3)})

    operational = float(np.clip(sum(s["weight"] * s["strength"] for s in operational_signals), 0.0, 1.0))

    # mutual softening: a strongly operational story reduces suspicion and vice versa
    suspicious_adj = float(np.clip(suspicious * (1.0 - 0.5 * operational), 0.0, 1.0))
    operational_adj = float(np.clip(operational * (1.0 - 0.35 * suspicious), 0.0, 1.0))

    return {
        "operational_drift_probability": round(operational_adj, 3),
        "suspicious_manipulation_probability": round(suspicious_adj, 3),
        "operational_signals": operational_signals,
        "suspicious_signals": signals,
        "raw": {
            "operational": round(operational, 3),
            "suspicious": round(suspicious, 3),
            "context_psi_scaled_avg": round(context_psi, 2),
        },
    }
