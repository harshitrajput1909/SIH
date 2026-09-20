"""Application configuration (environment-driven, offline by default)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TVD_", env_file=None, extra="ignore")

    app_name: str = "TRUSTVISION Distribution Shift Engine"
    version: str = "1.0.0"
    offline: bool = True

    api_key: str | None = None
    cors_origins: list[str] = []
    workspace_dir: Path = Path("workspace")
    max_upload_bytes: int = 10 * 1024**3
    log_level: str = "INFO"

    # --- sampling -----------------------------------------------------------
    max_samples_per_side: int = 20_000
    feature_size: int = 96                  # working resolution for visual features
    min_side_samples: int = 20              # below this a side cannot be assessed
    seed: int = 20260919

    # --- statistics ---------------------------------------------------------
    psi_bins: int = 10
    psi_epsilon: float = 1e-4
    psi_moderate: float = 0.10
    psi_significant: float = 0.25
    domain_cv_folds: int = 4
    domain_min_side: int = 40               # min per side for the classifier test

    # --- disentangulation thresholds ---------------------------------------
    suspicious_class_tvd: float = 0.20      # class drift with metadata continuity
    suspicious_share_jump: float = 0.15     # single-class share jump
    suspicious_concentration: float = 0.60  # share of |Δ| mass in top class
    suspicious_exif_strip_gap: float = 0.30 # candidate EXIF missing - reference missing
    suspicious_dup_rate: float = 0.10       # exact/near duplicate rate in candidate
    evidence_limit: int = 12
