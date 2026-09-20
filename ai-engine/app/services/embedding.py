"""Consensus model: a small CNN trained in-sandbox on the dataset's own labels.

Purpose (no external weights — fully offline):
  * out-of-fold (OOF) predictions provide an independent "consensus" against
    which the provided labels are checked (label flips, systematic mislabelling);
  * penultimate-layer embeddings feed the OOD detector.

The model is deliberately tiny (GroupNorm CNN, CPU-friendly) and trained with
stratified K-fold cross-validation so every covered sample receives an
out-of-fold prediction that never saw its own label.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor, nn
from torch.utils.data import DataLoader, Dataset

from app.core.errors import AnalysisError
from app.core.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------


class ConsensusNet(nn.Module):
    def __init__(self, num_classes: int, emb_dim: int = 64) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, 3, padding=1), nn.GroupNorm(4, 16), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.GroupNorm(8, 32), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.GroupNorm(8, 64), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.GroupNorm(16, 128), nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
        )
        self.embed = nn.Linear(128, emb_dim)
        self.classifier = nn.Linear(emb_dim, num_classes)

    def forward(self, x: Tensor) -> Tensor:
        z = F.relu(self.embed(self.features(x)))
        return self.classifier(z)

    def embedding(self, x: Tensor) -> Tensor:
        return F.relu(self.embed(self.features(x)))


# ---------------------------------------------------------------------------
# data access
# ---------------------------------------------------------------------------


class ImageStore:
    """Lazy image access with an optional per-sample decoded cache."""

    def __init__(self, samples: list, image_size: int) -> None:
        self.samples = samples
        self.image_size = image_size
        self._cache = {s.idx: s.image for s in samples if s.image is not None}

    def array(self, idx: int) -> np.ndarray:
        """RGB uint8 HWC at engine resolution."""
        arr = self._cache.get(idx)
        if arr is not None:
            return arr
        sample = self.samples[idx]
        data = sample.abs_path.read_bytes()
        arr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            raise AnalysisError(f"image became unreadable: {sample.abs_path}")
        arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        return cv2.resize(arr, (self.image_size, self.image_size), interpolation=cv2.INTER_AREA)

    def tensor(self, idx: int) -> Tensor:
        arr = np.ascontiguousarray(self.array(idx).transpose(2, 0, 1))
        return torch.from_numpy(arr).float() / 255.0


class IndexedDataset(Dataset):
    def __init__(self, store: ImageStore, indices: list[int], labels: list[int]) -> None:
        self.store = store
        self.indices = indices
        self.labels = labels

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, i: int) -> tuple[Tensor, Tensor]:
        x = self.store.tensor(self.indices[i])
        return x, torch.tensor(self.labels[i], dtype=torch.long)


# ---------------------------------------------------------------------------
# training / inference
# ---------------------------------------------------------------------------


@dataclass
class ConsensusOutputs:
    class_ids: list[int]          # original label ids covered by the model
    oof_probs: np.ndarray         # (N, C) out-of-fold probabilities, NaN = uncovered
    oof_emb: np.ndarray           # (N, emb_dim) OOF embeddings, NaN = uncovered
    folds: int
    elig_idx: np.ndarray          # global indices of covered samples
    y: np.ndarray                 # remapped labels (0..C-1) aligned with elig_idx


def train_fold(
    store: ImageStore,
    train_idx: np.ndarray,
    y_train: np.ndarray,
    num_classes: int,
    cfg,
    fold_seed: int,
) -> ConsensusNet:
    torch.manual_seed(cfg.seed + fold_seed)
    np.random.seed((cfg.seed + fold_seed) % (2**31))

    model = ConsensusNet(num_classes, cfg.emb_dim)
    dataset = IndexedDataset(store, train_idx.tolist(), y_train.tolist())
    batch_size = min(cfg.batch_size, max(2, len(dataset)))
    drop_last = len(dataset) >= batch_size and (len(dataset) % batch_size != 1)
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        drop_last=drop_last,
        generator=torch.Generator().manual_seed(cfg.seed + fold_seed),
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.lr)

    # Small datasets give few steps per epoch; scale epochs up (bounded) so the
    # consensus model actually converges instead of outputting the class prior.
    steps_per_epoch = max(1, math.ceil(len(dataset) / batch_size))
    epochs = min(40, max(cfg.epochs, math.ceil(cfg.min_train_steps / steps_per_epoch)))

    model.train()
    for _ in range(epochs):
        for xb, yb in loader:
            optimizer.zero_grad()
            loss = F.cross_entropy(model(xb), yb)
            loss.backward()
            optimizer.step()
    return model


def infer(
    model: ConsensusNet,
    store: ImageStore,
    indices: list[int],
    num_classes: int,
    batch_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    probs = np.zeros((len(indices), num_classes), np.float32)
    emb = np.zeros((len(indices), model.embed.out_features), np.float32)
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            chunk = indices[start : start + batch_size]
            x = torch.stack([store.tensor(i) for i in chunk])
            e = model.embedding(x)
            logits = model.classifier(e)
            probs[start : start + len(chunk)] = torch.softmax(logits, dim=1).cpu().numpy()
            emb[start : start + len(chunk)] = e.cpu().numpy()
    return probs, emb


def build_consensus(
    samples: list,
    labels_arr: np.ndarray,
    cfg,
    progress,
) -> ConsensusOutputs | None:
    """Train stratified K-fold consensus models. Returns None when the dataset
    is too small / too few classes for a meaningful consensus."""
    from collections import Counter

    counts = Counter(int(v) for v in labels_arr if v >= 0)
    eligible = sorted(c for c, cnt in counts.items() if cnt >= cfg.min_class_samples)
    if len(eligible) < cfg.min_consensus_classes:
        log.info("consensus skipped: only %d classes with >=%d samples", len(eligible), cfg.min_class_samples)
        return None
    class_to_col = {c: i for i, c in enumerate(eligible)}
    elig_idx = np.array(
        [s.idx for s in samples if s.label_id is not None and s.label_id in class_to_col],
        dtype=np.int64,
    )
    y = np.array([class_to_col[int(labels_arr[i])] for i in elig_idx], dtype=np.int64)

    min_count = min(counts[c] for c in eligible)
    n_folds = min(cfg.folds, min_count)
    if n_folds < 2:
        return None

    num = len(samples)
    oof_probs = np.full((num, len(eligible)), np.nan, np.float32)
    oof_emb = np.full((num, cfg.emb_dim), np.nan, np.float32)
    store = ImageStore(samples, cfg.image_size)

    skf = StratifiedKFoldCompat(n_splits=n_folds, seed=cfg.seed)
    splits = list(skf.split(elig_idx, y))
    for k, (tr, te) in enumerate(splits):
        progress(f"consensus-train-fold-{k + 1}-of-{n_folds}", k / n_folds)
        model = train_fold(store, elig_idx[tr], y[tr], len(eligible), cfg, k)
        probs, emb = infer(model, store, elig_idx[te].tolist(), len(eligible), cfg.batch_size)
        oof_probs[elig_idx[te]] = probs
        oof_emb[elig_idx[te]] = emb
    progress("consensus-complete", 1.0)
    log.info("consensus trained: %d classes, %d covered samples, %d folds", len(eligible), len(elig_idx), n_folds)
    return ConsensusOutputs(
        class_ids=eligible, oof_probs=oof_probs, oof_emb=oof_emb, folds=n_folds,
        elig_idx=elig_idx, y=y,
    )


class StratifiedKFoldCompat:
    """Deterministic stratified K-fold (sklearn StratifiedKFold wrapper)."""

    def __init__(self, n_splits: int, seed: int) -> None:
        from sklearn.model_selection import StratifiedKFold

        self._impl = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)

    def split(self, x: np.ndarray, y: np.ndarray):
        return self._impl.split(x, y)
