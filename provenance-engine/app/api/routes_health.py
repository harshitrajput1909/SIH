"""Service health."""

from __future__ import annotations

import platform

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.keys import get_key_manager

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    keys = get_key_manager()
    return {
        "status": "ok",
        "service": "trustvision-provenance-engine",
        "version": settings.version,
        "offline": settings.offline,
        "signature": {
            "algorithm": "Ed25519",
            "key_id": keys.key_id,
            "public_key": keys.public_key_hex,
        },
        "runtime": {"python": platform.python_version()},
    }
