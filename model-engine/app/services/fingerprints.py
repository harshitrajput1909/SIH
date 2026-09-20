"""Model fingerprinting: file, weight-digest and architecture fingerprints."""

from __future__ import annotations

import hashlib

import numpy as np

from app.schemas import FingerprintDto


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_fingerprint(path, sha256: str) -> FingerprintDto:
    return FingerprintDto(type="FILE_SHA256", value=sha256, detail={"path": str(path)})


def weight_digest(tensors: dict[str, np.ndarray]) -> FingerprintDto | None:
    """Digest over the canonical serialization of all tensors (sorted by name).
    Stable across re-saves with the same values, sensitive to any weight change."""
    if not tensors:
        return None
    digest = hashlib.sha256()
    for name in sorted(tensors):
        arr = np.ascontiguousarray(tensors[name])
        digest.update(name.encode())
        digest.update(str(arr.dtype).encode())
        digest.update(str(arr.shape).encode())
        digest.update(arr.tobytes())
    return FingerprintDto(
        type="WEIGHT_SHA256",
        value=digest.hexdigest(),
        detail={"tensor_count": len(tensors)},
    )


def architecture_hash(graph_info: dict) -> FingerprintDto | None:
    if not graph_info:
        return None
    import json

    canonical = json.dumps(graph_info, sort_keys=True, default=str)
    kind = str(graph_info.get("kind", "onnx"))
    return FingerprintDto(
        type="ONNX_GRAPH_HASH" if kind != "torchscript" else "TORCHSCRIPT_CODE_HASH",
        value=_sha(canonical.encode()),
        detail={"kind": kind},
    )


def compare(ours: list[FingerprintDto], reference: list[FingerprintDto]) -> dict:
    ours_map = {f.type: f.value for f in ours}
    ref_map = {f.type: f.value for f in reference}
    return {
        ftype: {
            "match": ours_map.get(ftype) == ref_map.get(ftype),
            "candidate": ours_map.get(ftype),
            "reference": ref_map.get(ftype),
        }
        for ftype in sorted(set(ours_map) | set(ref_map))
    }
