"""Service health & capability discovery."""

from __future__ import annotations

import platform

import numpy as np
import torch
from fastapi import APIRouter

from app.core.config import get_settings
from app.services.assessment import CAPABILITIES

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "trustvision-model-engine",
        "version": settings.version,
        "offline": settings.offline,
        "capabilities": CAPABILITIES,
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "torch_threads": settings.torch_threads,
        },
    }
