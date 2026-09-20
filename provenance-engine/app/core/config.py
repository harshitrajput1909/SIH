"""Application configuration (environment-driven, offline by default)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TVP_", env_file=None, extra="ignore")

    app_name: str = "TRUSTVISION Provenance Engine"
    version: str = "1.0.0"
    offline: bool = True

    api_key: str | None = None
    cors_origins: list[str] = []
    workspace_dir: Path = Path("workspace")
    log_level: str = "INFO"

    signing_key_path: Path | None = None
    ledger_path: Path | None = None

    @property
    def resolved_signing_key_path(self) -> Path:
        return self.signing_key_path or (self.workspace_dir / "keys" / "signing.pem")

    @property
    def resolved_ledger_path(self) -> Path:
        return self.ledger_path or (self.workspace_dir / "provenance" / "ledger.jsonl")


@lru_cache
def get_settings() -> Settings:
    return Settings()
