"""Pydantic schemas for the provenance engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateFromPathsRequest(BaseModel):
    image_path: str
    model_path: str
    output_path: str | None = None
    config: dict[str, Any] | None = None
    config_path: str | None = None
    nonce: str | None = Field(None, max_length=128)


class VerifyRequest(BaseModel):
    record: dict[str, Any] | None = None
    record_id: str | None = None
    supplied_hashes: dict[str, str] | None = Field(
        None,
        description=(
            "Re-supplied artifact hashes to compare against the committed values "
            "(keys: input_sha256, model_sha256, config_sha256, output_sha256)."
        ),
    )


class VerificationResult(BaseModel):
    record_id: str | None
    valid: bool
    checks: dict[str, bool]
    details: dict[str, Any] = {}
    verified_at: str


class ChainResponse(BaseModel):
    length: int
    chain_ok: bool
    issues: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
