"""Trigger (backdoor) injection detection.

Looks for a localized patch pattern that recurs across several images, sits in
a consistent grid cell, and is rare inside its own class — the classic shape of
a planted trigger. Runs independently of the consensus model; label-flip
suspects are always scanned first.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import random

import cv2
import numpy as np

from app.schemas import EvidenceItem, Finding, RiskLevel
from app.services.hashing import phash64

GRID = 4  # 4x4 patch grid over the engine-resolution image


def _corners(r: int, c: int) -> bool:
    return r in (0, GRID - 1) and c in (0, GRID - 1)


def detect_trigger_injection(
    samples: list,
    store,
    exclude_mask: np.ndarray,
    suspects: list[int],
    cfg,
) -> tuple[list[Finding], np.ndarray]:
    """Returns (findings, per-sample flags).

    ``exclude_mask`` masks samples already explained by duplicate/flooding/OOD
    findings (repeated imagery produces trivially recurring patches).
    """
    n = len(samples)
    flags = np.zeros(n, dtype=bool)
    findings: list[Finding] = []
    if n == 0:
        return findings, flags

    # scan set: all un-excluded images (capped deterministically) + all suspects
    candidates = [i for i in range(n) if not exclude_mask[i]]
    if len(candidates) > cfg.trigger_scan_cap:
        rng = random.Random(cfg.seed)
        candidates = sorted(rng.sample(candidates, cfg.trigger_scan_cap))
    scan = sorted(set(candidates) | set(suspects))

    cell = cfg.image_size // GRID
    groups: dict[tuple, list[int]] = defaultdict(list)
    for idx in scan:
        rgb = store.array(idx)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        for r in range(GRID):
            for c in range(GRID):
                patch_gray = gray[r * cell : (r + 1) * cell, c * cell : (c + 1) * cell]
                uniform = bool(patch_gray.std() < 8.0)
                # pHash of ANY constant patch is all-zeros (DC is discarded), so
                # uniform cells must additionally be keyed by quantized mean
                # colour — otherwise white/black/blue triggers collapse together.
                color_key = None
                if uniform:
                    means = rgb[r * cell : (r + 1) * cell, c * cell : (c + 1) * cell].reshape(-1, 3).mean(axis=0)
                    color_key = tuple(int(v // 48) for v in means)
                key = (r, c, phash64(patch_gray), uniform, color_key)
                groups[key].append(idx)

    for (r, c, pattern_hash, uniform, color_key), idxs in groups.items():
        distinct = len(set(idxs))
        if distinct < cfg.trigger_min_images:
            continue
        contributors = [samples[i].contributor for i in idxs]
        top_contributor, contributor_share = Counter(contributors).most_common(1)[0]

        labelled = [samples[i].label_name for i in idxs if samples[i].label_id is not None]
        class_share_ok = True
        class_name = None
        if labelled:
            class_name, _ = Counter(labelled).most_common(1)[0]
            class_total = sum(1 for s in samples if s.label_name == class_name)
            class_share_ok = class_total == 0 or (distinct / class_total) <= cfg.trigger_max_class_share
        if not class_share_ok:
            continue  # pattern is common inside its class -> likely a real feature

        score = 0.4 + 0.06 * min(distinct, 10)
        if contributor_share >= 0.8:
            score += 0.15
        if uniform:
            score += 0.15
        if _corners(r, c):
            score += 0.10
        score = round(min(1.0, score), 3)

        severity = (
            RiskLevel.CRITICAL if distinct >= 10
            else RiskLevel.HIGH if distinct >= 6
            else RiskLevel.MEDIUM
        )
        findings.append(
            Finding(
                detector="trigger_injection",
                title=(
                    f"Recurring patch pattern at grid cell ({r},{c}) "
                    f"across {distinct} images"
                ),
                description=(
                    f"An {'approximately uniform' if uniform else 'identical'} patch recurs in "
                    f"cell ({r},{c}) across {distinct} images "
                    f"({top_contributor}: {contributor_share:.0%})"
                    + (f" labelled '{class_name}'" if class_name else "")
                    + ". Localized, position-consistent, class-rare patches are the classic "
                    "signature of a planted backdoor trigger."
                ),
                severity=severity,
                confidence=score,
                sample_count=distinct,
                contributors=sorted(set(contributors)),
                evidence=[
                    EvidenceItem(
                        kind="pattern",
                        image_paths=[samples[i].rel_path for i in idxs[: cfg.evidence_limit]],
                        contributor=top_contributor,
                        detail={
                            "grid_cell": f"({r},{c})",
                            "pattern_hash": f"{pattern_hash:016x}",
                            "uniform_patch": uniform,
                            "images": distinct,
                        },
                    )
                ],
                detail={
                    "grid_cell": f"({r},{c})",
                    "pattern_hash": f"{pattern_hash:016x}",
                    "images": distinct,
                    "uniform_patch": uniform,
                },
            )
        )
        flags[idxs] = True

    return findings, flags
