"""Deterministic probe generation and input perturbation utilities."""

from __future__ import annotations

import numpy as np

from app.services.model_loading import InputSpec


def make_probes(specs: list[InputSpec], count: int, seed: int) -> list[list[np.ndarray]]:
    """Reference test battery inputs: fixed edge cases + seeded random probes."""
    rng = np.random.default_rng(seed)
    probes: list[list[np.ndarray]] = []

    def build(fillers) -> list[np.ndarray]:
        return [
            np.ascontiguousarray(fillers(spec), dtype=spec.dtype)
            for spec in specs
        ]

    probes.append(build(lambda spec: np.zeros(spec.shape)))
    probes.append(build(lambda spec: np.ones(spec.shape)))
    probes.append(build(lambda spec: -np.ones(spec.shape)))

    for i in range(count):
        def fill(spec: InputSpec, i=i) -> np.ndarray:
            arr = rng.random(spec.shape)
            return (arr * 2 - 1) * (1 + i * 0.05)  # mild scale variation
        probes.append(build(fill))

    probes.append(build(lambda spec: np.full(spec.shape, 1e4, dtype=spec.dtype)))
    probes.append(build(lambda spec: np.full(spec.shape, 1e-6, dtype=spec.dtype)))

    # duplicate of the first random probe for the determinism check
    probes.append([p.copy() for p in probes[3]])
    return probes


def make_patched(
    base: list[np.ndarray],
    value: float = 1.0,
    grid: int = 4,
) -> list[tuple[str, list[np.ndarray]]]:
    """Spatial trigger patches for image-like inputs (NCHW/NDHWC/3-D+).

    Returns [(label, patched_inputs)] covering the 4 corners + centre.
    """
    patched: list[tuple[str, list[np.ndarray]]] = []
    first = base[0]
    if first.ndim < 3:
        return patched
    h = first.shape[-2] if first.ndim >= 3 else 0
    w = first.shape[-1] if first.ndim >= 3 else 0
    if h < 8 or w < 8:
        return patched
    side = max(2, min(h, w) // grid)

    positions = {
        "top-left": (0, 0),
        "top-right": (0, w - side),
        "bottom-left": (h - side, 0),
        "bottom-right": (h - side, w - side),
        "centre": ((h - side) // 2, (w - side) // 2),
    }
    for label, (r, c) in positions.items():
        variant = [arr.copy() for arr in base]
        for arr in variant:
            if arr.ndim == 4:
                arr[..., r : r + side, c : c + side] = value
            else:
                arr[r : r + side, c : c + side] = value
        patched.append((label, variant))
    return patched


def make_feature_toggles(
    base: list[np.ndarray],
    cap: int = 16,
    value: float = 1.0,
) -> list[tuple[str, list[np.ndarray]]]:
    """Feature-toggle probes for flat (1-D per sample) inputs."""
    first = base[0]
    if first.ndim != 2:
        return []
    features = min(first.shape[-1], cap)
    toggles: list[tuple[str, list[np.ndarray]]] = []
    for f in range(features):
        variant = [arr.copy() for arr in base]
        for arr in variant:
            arr[..., f] = value
        toggles.append((f"feature_{f}", variant))
    return toggles


def argmax_labels(output: np.ndarray) -> np.ndarray | None:
    """Prediction labels for 1-D multi-class outputs, else None."""
    flattened = output.reshape(output.shape[0], -1) if output.ndim >= 2 else output.reshape(1, -1)
    if flattened.shape[-1] < 2:
        return None
    return np.argmax(flattened, axis=-1)
