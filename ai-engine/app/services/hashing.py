"""Image hashing primitives: file SHA-256 and 64-bit perceptual hash (pHash)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def phash64(gray: np.ndarray) -> int:
    """64-bit perceptual hash (DCT-based, classic pHash) of a grayscale image.

    Works on any input size; the image is reduced to 32x32 before the DCT and
    the top-left 8x8 block (low frequencies) is thresholded at its median.
    """
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(small)
    block = dct[:8, :8].copy()
    flat = np.delete(block.reshape(-1), 0)          # exclude the DC term
    median = float(np.median(flat))
    bits = block > median
    bits[0, 0] = False
    value = 0
    for i, bit in enumerate(bits.flatten()):
        if bit:
            value |= 1 << i
    return value


def popcount_u64(values: np.ndarray) -> np.ndarray:
    """Vectorized Hamming weight for an array of uint64 values."""
    x = np.ascontiguousarray(values, dtype=np.uint64)
    byte_view = x.view(np.uint8).reshape(-1, 8)
    return np.unpackbits(byte_view, axis=1, bitorder="little").sum(axis=1, dtype=np.int32)


def hamming_distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")
