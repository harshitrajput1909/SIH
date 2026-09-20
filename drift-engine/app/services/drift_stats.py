"""Drift statistics: PSI (numeric + categorical), TVD, and the domain
two-sample classifier test."""

from __future__ import annotations

import numpy as np


def psi_numeric(reference: np.ndarray, candidate: np.ndarray, bins: int, epsilon: float) -> dict:
    """Population Stability Index using reference quantile bins.

    Returns {'psi': float, 'top_bin': int, 'ref_hist': [...], 'cand_hist': [...]}
    """
    reference = np.asarray(reference, dtype=np.float64)
    candidate = np.asarray(candidate, dtype=np.float64)
    if len(reference) == 0 or len(candidate) == 0:
        return {"psi": 0.0, "top_bin": -1, "ref_hist": [], "cand_hist": []}

    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:  # degenerate (constant feature) — nothing to drift
        return {"psi": 0.0, "top_bin": -1, "ref_hist": [1.0], "cand_hist": [1.0]}
    edges[0], edges[-1] = -np.inf, np.inf

    ref_idx = np.clip(np.digitize(reference, edges[1:-1]), 0, len(edges) - 2)
    cand_idx = np.clip(np.digitize(candidate, edges[1:-1]), 0, len(edges) - 2)

    n_bins = len(edges) - 1
    ref_hist = np.bincount(ref_idx, minlength=n_bins).astype(np.float64) / len(reference)
    cand_hist = np.bincount(cand_idx, minlength=n_bins).astype(np.float64) / len(candidate)

    contribution = (cand_hist - ref_hist) * np.log((cand_hist + epsilon) / (ref_hist + epsilon))
    psi = float(np.sum(contribution))
    return {
        "psi": psi,
        "top_bin": int(np.argmax(contribution)),
        "ref_hist": [round(v, 4) for v in ref_hist],
        "cand_hist": [round(v, 4) for v in cand_hist],
    }


def psi_categorical(reference: list, candidate: list, epsilon: float) -> dict:
    """PSI over category frequencies (union of categories)."""
    categories = sorted(set(reference) | set(candidate), key=str)
    if not categories:
        return {"psi": 0.0, "table": {}}
    ref_counts = {c: 0 for c in categories}
    cand_counts = {c: 0 for c in categories}
    for value in reference:
        ref_counts[value] += 1
    for value in candidate:
        cand_counts[value] += 1
    n_ref, n_cand = max(1, len(reference)), max(1, len(candidate))

    table = {}
    total = 0.0
    for category in categories:
        p = ref_counts[category] / n_ref
        q = cand_counts[category] / n_cand
        contribution = (q - p) * np.log((q + epsilon) / (p + epsilon))
        total += float(contribution)
        table[str(category)] = {
            "ref_share": round(p, 4),
            "cand_share": round(q, 4),
            "delta": round(q - p, 4),
        }
    return {"psi": total, "table": table}


def total_variation_distance(p: dict, q: dict) -> tuple[float, dict]:
    """TVD = 0.5 * Σ |p_i - q_i| over the union of keys; returns (tvd, per_key)."""
    keys = sorted(set(p) | set(q), key=str)
    per_key = {}
    total = 0.0
    for key in keys:
        pv, qv = p.get(key, 0.0), q.get(key, 0.0)
        delta = qv - pv
        per_key[str(key)] = round(delta, 4)
        total += abs(delta)
    return 0.5 * total, per_key


def domain_two_sample_test(x_ref: np.ndarray, x_cand: np.ndarray, folds: int, seed: int) -> dict:
    """Cross-validated AUC of a linear classifier separating ref(0) vs cand(1).

    AUC 0.5 → indistinguishable domains; 1.0 → fully separated.
    drift = 2*(AUC - 0.5) ∈ [0, 1].
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    n_min = min(len(x_ref), len(x_cand))
    if n_min < 20:
        return {"ran": False, "reason": f"insufficient samples ({n_min} < 20)"}

    # balance the classes so AUC is not skewed by side size
    rng = np.random.default_rng(seed)
    take = min(len(x_ref), len(x_cand))
    ref_idx = rng.choice(len(x_ref), size=take, replace=False)
    cand_idx = rng.choice(len(x_cand), size=take, replace=False)

    x = np.vstack([x_ref[ref_idx], x_cand[cand_idx]])
    y = np.concatenate([np.zeros(take), np.ones(take)])

    n_folds = max(2, min(folds, take // 10))
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=300, C=1.0),
    )
    try:
        scores = cross_val_score(model, x, y, cv=n_folds, scoring="roc_auc")
    except Exception as exc:  # pragma: no cover - numerical edge
        return {"ran": False, "reason": f"classifier test failed: {exc}"}

    auc = float(np.mean(scores))
    drift = max(0.0, min(1.0, 2.0 * (auc - 0.5)))
    return {
        "ran": True,
        "auc": round(auc, 4),
        "drift": round(drift, 4),
        "folds": n_folds,
        "n_per_side": int(take),
    }


def duplicate_rate(phashes: list[int]) -> float:
    """Fraction of images whose pHash appears more than once on the same side."""
    if not phashes:
        return 0.0
    counts: dict[int, int] = {}
    for value in phashes:
        counts[value] = counts.get(value, 0) + 1
    duplicated = sum(c for c in counts.values() if c > 1)
    return duplicated / len(phashes)
