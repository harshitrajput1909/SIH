"""TRUSTVISION Model Integrity Engine — FastAPI application factory."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import torch
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_assessment, routes_health
from app.core.config import get_settings
from app.core.errors import AnalysisError
from app.core.logging import configure_logging, get_logger
from app.core.security import require_api_key

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(settings.torch_threads)
    log.info("engine ready (offline=%s, threads=%d)", settings.offline, settings.torch_threads)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    if settings.offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Offline model integrity assessment for ONNX / PyTorch / TorchScript artefacts: "
            "white-box parameter, activation, layer and fingerprint checks; black-box "
            "behavioural fingerprinting, reference batteries, output consistency and "
            "backdoor probing."
        ),
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(routes_health.router)
    app.include_router(routes_assessment.router, dependencies=[Depends(require_api_key)])

    @app.exception_handler(AnalysisError)
    async def analysis_error_handler(_: Request, exc: AnalysisError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    return app


app = create_app()
