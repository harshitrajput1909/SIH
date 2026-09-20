"""Application configuration (environment-driven, offline by default)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TVMI_", env_file=None, extra="ignore")

    app_name: str = "TRUSTVISION Model Integrity Engine"
    version: str = "1.0.0"
    offline: bool = True

    api_key: str | None = None
    cors_origins: list[str] = []
    workspace_dir: Path = Path("workspace")
    max_model_bytes: int = 2 * 1024**3
    log_level: str = "INFO"

    # --- runtime ------------------------------------------------------------
    torch_threads: int = max(1, (os.cpu_count() or 2) // 2)
    seed: int = 20260919
    allow_pickle_execution: bool = False   # torch.load(weights_only=False) gate
    probe_count: int = 10                  # random probes in the reference battery

    # --- assessment thresholds ---------------------------------------------
    divergence_threshold: float = 0.30     # behavioural divergence -> substitution
    agreement_threshold: float = 0.70      # argmax agreement floor
    backdoor_flip_medium: float = 0.10
    backdoor_flip_high: float = 0.25
    backdoor_concentration: float = 0.60
    extreme_weight_magnitude: float = 1e6
    max_modules_hooked: int = 200


@lru_cache
def get_settings() -> Settings:
    return Settings()
