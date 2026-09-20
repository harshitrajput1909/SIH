"""Visual feature extraction (single pass per image, CPU-light)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

# Feature vector order — used by the domain two-sample test.
FEATURE_NAMES = [
    "brightness", "contrast", "saturation", "edge_density", "sharpness",
    "green_ratio", "warm_ratio", "snow_ratio", "blue_ratio", "gray_ratio",
    "dark_ratio", "bright_ratio",
]


def decode_bgr(path: Path, size: int):
    data = Path(path).read_bytes()
    arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        return None
    return cv2.resize(arr, (size, size), interpolation=cv2.INTER_AREA)


def phash64(gray: np.ndarray) -> int:
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(small)
    block = dct[:8, :8].copy()
    flat = np.delete(block.reshape(-1), 0)
    median = float(np.median(flat))
    bits = block > median
    bits[0, 0] = False
    value = 0
    for i, bit in enumerate(bits.flatten()):
        if bit:
            value |= 1 << i
    return value


def extract_feature_vector(bgr: np.ndarray) -> np.ndarray:
    """12-dim visual descriptor used for drift statistics."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    b_ch, g_ch, r_ch = bgr[..., 0].astype(np.int16), bgr[..., 1].astype(np.int16), bgr[..., 2].astype(np.int16)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    edges = cv2.Canny(gray, 80, 160)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    green = float(((hue >= 35) & (hue <= 85) & (sat > 60) & (val > 40)).mean())
    warm = float(((r_ch - b_ch) > 25).mean())
    snow = float(((val > 200) & (sat < 30)).mean())
    blue = float(((hue >= 100) & (hue <= 130) & (sat > 50)).mean())
    grayish = float(((sat < 40) & (val > 40) & (val < 200)).mean())
    dark = float((val < 50).mean())
    bright = float((val > 160).mean())

    return np.array([
        float(val.mean()), float(val.std()), float(sat.mean()),
        float(edges.mean()) / 255.0, sharpness,
        green, warm, snow, blue, grayish, dark, bright,
    ], dtype=np.float64)


def load_matrix(side, size: int) -> tuple[np.ndarray, list[str]]:
    """Feature matrix (N, 12) + aligned rel paths."""
    rows: list[np.ndarray] = []
    paths: list[str] = []
    for sample in side.samples:
        bgr = decode_bgr(sample.abs_path, size)
        if bgr is None:
            continue
        rows.append(extract_feature_vector(bgr))
        paths.append(sample.rel_path)
    if not rows:
        return np.zeros((0, len(FEATURE_NAMES))), []
    return np.stack(rows), paths
