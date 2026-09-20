"""Context slicing: terrain, season, sensor and illumination signals.

Each slice uses EXIF metadata when available and a visual proxy otherwise,
so unannotated imagery is still assessed (with a stated limitation).
"""

from __future__ import annotations

from collections import Counter
from typing import Callable

import numpy as np

from app.services.features import FEATURE_NAMES


def _slice_values(side, matrix: np.ndarray, classifier: Callable[[np.ndarray, dict], str]) -> list[str]:
    """Assign a slice tag per sample using its feature row + EXIF tags."""
    feature_index = {name: i for i, name in enumerate(FEATURE_NAMES)}
    values: list[str] = []
    for row, sample in zip(matrix, side.samples):
        exif = side.exif.get(sample.rel_path, {})
        values.append(classifier(row, {"features": feature_index, "exif": exif, "path": sample.abs_path}))
    return values


def _row(row: np.ndarray, name: str, ctx: dict) -> float:
    return float(row[ctx["features"][name]])


# ---------------------------------------------------------------------------
# terrain
# ---------------------------------------------------------------------------


def classify_terrain(row: np.ndarray, ctx: dict) -> str:
    green = _row(row, "green_ratio", ctx)
    snow = _row(row, "snow_ratio", ctx)
    blue = _row(row, "blue_ratio", ctx)
    warm = _row(row, "warm_ratio", ctx)
    gray = _row(row, "gray_ratio", ctx)
    edges = _row(row, "edge_density", ctx)

    if snow > 0.12:
        return "snow"
    if green > 0.25 and edges < 0.10:
        return "vegetation"
    if blue > 0.25:
        return "water"
    if warm > 0.45 and green < 0.20:
        return "arid"
    if gray > 0.40 or edges > 0.09:
        return "urban"
    return "mixed"


# ---------------------------------------------------------------------------
# season (EXIF month when present, visual proxy otherwise)
# ---------------------------------------------------------------------------

_SEASON_BY_MONTH = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}


def classify_season(row: np.ndarray, ctx: dict) -> str:
    month = ctx["exif"].get("month")
    if isinstance(month, int) and 1 <= month <= 12:
        return _SEASON_BY_MONTH[month]
    snow = _row(row, "snow_ratio", ctx)
    green = _row(row, "green_ratio", ctx)
    warm = _row(row, "warm_ratio", ctx)
    brightness = _row(row, "brightness", ctx)
    if snow > 0.12:
        return "winter"
    if green > 0.28 and brightness > 90:
        return "summer"
    if warm > 0.40 and green < 0.18:
        return "autumn"
    if green > 0.15:
        return "spring"
    return "indeterminate"


# ---------------------------------------------------------------------------
# sensor (EXIF make/model when present, resolution+noise proxy otherwise)
# ---------------------------------------------------------------------------


def classify_sensor(row: np.ndarray, ctx: dict) -> str:
    make = ctx["exif"].get("make")
    model = ctx["exif"].get("model")
    if make or model:
        return f"exif:{str(make or '')}/{str(model or '')}".strip("/")
    sharpness = _row(row, "sharpness", ctx)
    noise_bucket = "low" if sharpness < 200 else "medium" if sharpness < 800 else "high"
    return f"visual:{noise_bucket}-noise"


# ---------------------------------------------------------------------------
# illumination (EXIF flash/exposure hints, visual luminance otherwise)
# ---------------------------------------------------------------------------


def classify_illumination(row: np.ndarray, ctx: dict) -> str:
    brightness = _row(row, "brightness", ctx)
    flash = ctx["exif"].get("flash")
    if brightness < 45:
        return "night"
    if brightness < 90:
        return "low-light"
    if brightness > 170:
        return "overexposed" if flash is True else "bright-day"
    return "normal-day"


# ---------------------------------------------------------------------------
# helpers for reporting
# ---------------------------------------------------------------------------


def proportions(values: list[str]) -> dict[str, float]:
    counts = Counter(values)
    total = max(1, len(values))
    return {key: count / total for key, count in counts.items()}


def metadata_coverage(side) -> float:
    if not side.exif:
        return 0.0
    return sum(1 for tags in side.exif.values() if tags) / len(side.exif)


def exif_months(side) -> list[int]:
    months = []
    for tags in side.exif.values():
        month = tags.get("month")
        if isinstance(month, int):
            months.append(month)
    return months


def exif_missing_rate(side) -> float:
    if not side.exif:
        return 1.0
    return 1.0 - metadata_coverage(side)
