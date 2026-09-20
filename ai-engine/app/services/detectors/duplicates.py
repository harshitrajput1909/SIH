"""Duplicate detection: exact copies (SHA-256) and verified near duplicates.

Near-duplicate detection is two-stage: pHash Hamming distance proposes
candidates (cheap, recall-oriented), then a pixel-level mean-absolute-
difference check confirms them (precision). The confirmation rejects images
that merely share composition (same class, similar layout) — which otherwise
mass-clone in synthetic/low-diversity corpora — while still catching re-encoded,
brightness-adjusted or lightly edited re-submissions.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np

from app.core.logging import get_logger
from app.schemas import EvidenceItem, Finding, RiskLevel

log = get_logger(__name__)

MAX_BUCKET_SCAN = 400  # cap per-band bucket to bound candidate pair explosion


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, a: int) -> int:
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _popcount(values: np.ndarray) -> np.ndarray:
    byte_view = np.ascontiguousarray(values, dtype=np.uint64).view(np.uint8).reshape(-1, 8)
    return np.unpackbits(byte_view, axis=1, bitorder="little").sum(axis=1, dtype=np.int32)


def _severity(size: int) -> RiskLevel:
    if size >= 10:
        return RiskLevel.CRITICAL
    if size >= 4:
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


def detect_duplicates(samples: list, cfg, store) -> tuple[list[Finding], list[list[int]], np.ndarray]:
    """Returns (findings, clusters, per-sample flags).

    ``store`` must expose ``array(idx) -> RGB uint8 array`` for the pixel-level
    near-duplicate confirmation.
    """
    n = len(samples)
    flags = np.zeros(n, dtype=bool)
    if n == 0:
        return [], [], flags

    uf = _UnionFind(n)
    phashes = np.array([s.phash for s in samples], dtype=np.uint64)

    # exact duplicates (identical file bytes) — no pixel check needed
    by_sha: dict[str, list[int]] = defaultdict(list)
    for sample in samples:
        by_sha[sample.sha256].append(sample.idx)
    for group in by_sha.values():
        if len(group) >= 2:
            for other in group[1:]:
                uf.union(group[0], other)

    # near duplicates: 8-band locality candidates -> Hamming filter -> pixel MAD
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for sample in samples:
        h = sample.phash
        for band in range(8):
            buckets[(band, (h >> (16 * band)) & 0xFFFF)].append(sample.idx)
    candidates: set[tuple[int, int]] = set()
    for idxs in buckets.values():
        if len(idxs) < 2:
            continue
        idxs = sorted(idxs)[:MAX_BUCKET_SCAN]
        for a, b in combinations(idxs, 2):
            candidates.add((a, b) if a < b else (b, a))

    verified = 0
    if candidates:
        ca = np.fromiter((p[0] for p in sorted(candidates)), dtype=np.int64, count=len(candidates))
        cb = np.fromiter((p[1] for p in sorted(candidates)), dtype=np.int64, count=len(candidates))
        hamming = _popcount(phashes[ca] ^ phashes[cb])
        similar = np.nonzero(hamming <= cfg.near_dup_hamming)[0]
        mad_cache: dict[int, np.ndarray] = {}

        def _array(idx: int) -> np.ndarray:
            if idx not in mad_cache:
                mad_cache[idx] = store.array(idx)
            return mad_cache[idx]

        for j in similar:
            a, b = int(ca[j]), int(cb[j])
            diff = np.abs(
                _array(a).astype(np.int16) - _array(b).astype(np.int16)
            ).mean()
            if diff <= cfg.dup_max_mad:
                uf.union(a, b)
                verified += 1
    log.debug("near-duplicate candidates verified: %d pairs", verified)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(i)
    clusters = sorted((m for m in groups.values() if len(m) >= 2), key=len, reverse=True)

    findings: list[Finding] = []
    for cluster in clusters:
        distinct_sha = len({samples[i].sha256 for i in cluster})
        kind = "exact duplicate" if distinct_sha == 1 else "near-duplicate"
        contributors = sorted({samples[i].contributor for i in cluster})
        findings.append(
            Finding(
                detector="duplicate_detection",
                title=f"{kind.capitalize()} group ({len(cluster)} images)",
                description=(
                    f"{len(cluster)} images share visual content "
                    f"({distinct_sha} distinct file hashes)."
                ),
                severity=_severity(len(cluster)),
                confidence=1.0 if distinct_sha == 1 else 0.95,
                sample_count=len(cluster),
                contributors=contributors,
                evidence=[
                    EvidenceItem(
                        kind="cluster",
                        image_paths=[samples[i].rel_path for i in cluster[: cfg.evidence_limit]],
                        contributor=contributors[0] if len(contributors) == 1 else None,
                        detail={"images": len(cluster), "distinct_files": distinct_sha},
                    )
                ],
                detail={"cluster_size": len(cluster), "distinct_files": distinct_sha},
            )
        )
        flags[cluster] = True

    return findings, clusters, flags
