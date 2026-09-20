"""Provenance record creation, verification and chain inspection."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.core.errors import ReplayAttackError
from app.core.logging import get_logger
from app.schemas import ChainResponse, CreateFromPathsRequest, VerificationResult, VerifyRequest
from app.services.keys import get_key_manager
from app.services.ledger import get_ledger
from app.services.provenance import ProvenanceService

router = APIRouter(prefix="/api/v1/provenance", tags=["provenance"])
log = get_logger(__name__)


def _service() -> ProvenanceService:
    return ProvenanceService(get_ledger(), get_key_manager())


# ---------------------------------------------------------------------------
# creation
# ---------------------------------------------------------------------------


@router.post("/records", status_code=201)
def create_from_paths(request: CreateFromPathsRequest) -> dict:
    for label, path in (("image_path", request.image_path), ("model_path", request.model_path)):
        if not Path(path).exists():
            raise HTTPException(status_code=422, detail=f"{label} does not exist: {path}")
    if request.config_path and not Path(request.config_path).exists():
        raise HTTPException(status_code=422, detail=f"config_path does not exist: {request.config_path}")
    if request.output_path and not Path(request.output_path).exists():
        raise HTTPException(status_code=422, detail=f"output_path does not exist: {request.output_path}")
    try:
        return _service().create_from_paths(
            image_path=Path(request.image_path),
            model_path=Path(request.model_path),
            config=request.config,
            config_path=Path(request.config_path) if request.config_path else None,
            output_path=Path(request.output_path) if request.output_path else None,
            client_nonce=request.nonce,
        )
    except ReplayAttackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/records/upload", status_code=201)
async def create_from_upload(
    image: UploadFile,
    model: UploadFile,
    output: UploadFile | None = None,
    config_json: str | None = None,
    nonce: str | None = None,
) -> dict:
    settings_workdir = Path("workspace") / "uploads" / uuid.uuid4().hex[:12]
    workdir = settings_workdir
    workdir.mkdir(parents=True, exist_ok=True)

    def _save(upload: UploadFile, name: str) -> Path:
        target = workdir / name
        with target.open("wb") as out:
            out.write(upload.file.read())
        return target

    try:
        config_payload = json.loads(config_json) if config_json else None
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"config_json is not valid JSON: {exc}") from exc

    config_file = workdir / "config.json"
    if config_payload is not None:
        config_file.write_text(json.dumps(config_payload, sort_keys=True), encoding="utf-8")

    try:
        return _service().create_from_paths(
            image_path=_save(image, "input_image"),
            model_path=_save(model, "model"),
            config=config_payload,
            config_path=config_file if config_payload is not None else None,
            output_path=_save(output, "output") if output is not None and output.filename else None,
            client_nonce=nonce,
        )
    except ReplayAttackError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------


@router.post("/verify", response_model=VerificationResult, response_model_exclude_none=True)
def verify(request: VerifyRequest) -> VerificationResult:
    if request.record is None and not request.record_id:
        raise HTTPException(status_code=422, detail="provide either 'record' or 'record_id'")
    if request.record is not None:
        presented = request.record
    else:
        stored = get_ledger().get(request.record_id)  # type: ignore[arg-type]
        if stored is None:
            raise HTTPException(status_code=404, detail=f"unknown record: {request.record_id}")
        presented = stored
    return _service().verify(presented, request.supplied_hashes)


@router.get("/records/{record_id}")
def get_record(record_id: str) -> dict:
    record = get_ledger().get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown record: {record_id}")
    return record


@router.get("/chain", response_model=ChainResponse, response_model_exclude_none=True)
def chain() -> ChainResponse:
    result = _service().chain()
    return ChainResponse(
        length=result["length"],
        chain_ok=result["chain_ok"],
        issues=result["issues"],
        records=result["records"],
    )
