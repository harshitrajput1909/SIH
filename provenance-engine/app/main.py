"""TRUSTVISION Provenance Engine — FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_health, routes_provenance
from app.core.config import get_settings
from app.core.errors import ReplayAttackError
from app.core.logging import configure_logging, get_logger
from app.core.security import require_api_key
from app.services.keys import get_key_manager
from app.services.ledger import get_ledger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    keys = get_key_manager()
    ledger = get_ledger()
    log.info(
        "engine ready (offline=%s, key_id=%s, ledger=%s, records=%d)",
        settings.offline, keys.key_id, ledger.path, len(ledger.records),
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Offline cryptographic provenance for inference records: SHA-256 commitments "
            "over image / model / configuration, server nonces, Ed25519 digital signatures, "
            "a hash-chained append-only ledger, and replay / tampering / output-substitution "
            "detection."
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
    app.include_router(routes_provenance.router, dependencies=[Depends(require_api_key)])

    @app.exception_handler(ReplayAttackError)
    async def replay_handler(_: Request, exc: ReplayAttackError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    return app


app = create_app()
