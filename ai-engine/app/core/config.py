"""Application configuration (environment-driven, offline by default)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Every field can be overridden with a ``TVA_`` env var."""

    model_config = SettingsConfigDict(env_prefix="TVA_", env_file=None, extra="ignore")

    app_name: str = "TRUSTVISION Dataset Assurance Engine"
    version: str = "1.0.0"
    offline: bool = True

    # --- service -----------------------------------------------------------
    api_key: str | None = None            # when set, requests must send X-API-Key
    cors_origins: list[str] = []
    workspace_dir: Path = Path("workspace")
    max_upload_bytes: int = 10 * 1024**3  # 10 GiB
    max_samples: int = 50_000
    log_level: str = "INFO"

    # --- consensus model (trained in-sandbox on the dataset itself) --------
    image_size: int = 96
    folds: int = 4
    epochs: int = 3
    batch_size: int = 64
    lr: float = 1e-3
    emb_dim: int = 64
    torch_threads: int = max(1, (os.cpu_count() or 2) // 2)
    seed: int = 20260919
    cache_images_max: int = 6_000         # decoded-image cache budget (samples)
    min_class_samples: int = 8            # per-class minimum for consensus training
    min_consensus_classes: int = 2
    min_train_steps: int = 60             # minimum optimizer steps per fold (small datasets)

    # --- detector thresholds ----------------------------------------------
    near_dup_hamming: int = 8             # pHash Hamming distance threshold
    dup_max_mad: float = 12.0             # pixel MAD confirmation for near dups
    flood_min_cluster: int = 5            # cluster size that counts as flooding
    flip_pred_prob: float = 0.55          # consensus prob. of the rival label
    flip_confidence_gap: float = 0.35     # p(rival) - p(given)
    mislabel_min_count: int = 10          # min samples for a systematic pattern
    mislabel_min_rate: float = 0.40       # min contributor confusion rate
    mislabel_z: float = 3.0               # one-proportion z threshold
    trigger_min_images: int = 3           # images sharing a patch pattern
    trigger_max_class_share: float = 0.50 # pattern must be rare inside its class
    trigger_scan_cap: int = 1_500         # max images grid-scanned per run
    ood_pct: float = 2.0                  # flagged OOD share of covered samples
    ood_min_train: int = 40               # min covered samples to fit OOD models
    ood_min_samples: int = 5              # hard minimum of OOD flags when firing
    evidence_limit: int = 25              # evidence items kept per finding

    # --- trust score weights ----------------------------------------------
    w_integrity: float = 0.30
    w_labelling: float = 0.30
    w_security: float = 0.20
    w_distribution: float = 0.20


@lru_cache
def get_settings() -> Settings:
    return Settings()
