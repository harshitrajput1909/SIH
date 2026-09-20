"""Canonical hashing primitives for the provenance chain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def canonical_bytes(obj) -> bytes:
    """Deterministic JSON serialization: sorted keys, no whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_canonical(obj) -> str:
    return sha256_hex(canonical_bytes(obj))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
