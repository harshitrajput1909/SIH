"""Provenance service: record creation, verification and chain inspection."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.core.errors import ReplayAttackError
from app.core.logging import get_logger
from app.services.hashing import canonical_bytes, sha256_file, sha256_hex
from app.services.keys import KeyManager
from app.services.ledger import Ledger

log = get_logger(__name__)

RECORD_TYPE = "INFERENCE_RECORD"


class ProvenanceService:
    def __init__(self, ledger: Ledger, keys: KeyManager) -> None:
        self.ledger = ledger
        self.keys = keys

    # ------------------------------------------------------------------
    # creation
    # ------------------------------------------------------------------

    def create_from_paths(
        self,
        image_path: Path,
        model_path: Path,
        config: dict[str, Any] | None = None,
        config_path: Path | None = None,
        output_path: Path | None = None,
        client_nonce: str | None = None,
    ) -> dict:
        for label, path in (("image", image_path), ("model", model_path)):
            if not Path(path).is_file():
                raise FileNotFoundError(f"{label} file not found: {path}")
        if config_path is not None and not Path(config_path).is_file():
            raise FileNotFoundError(f"config file not found: {config_path}")

        if client_nonce and self.ledger.nonce_owner(client_nonce):
            raise ReplayAttackError(
                f"nonce already bound to record {self.ledger.nonce_owner(client_nonce)}"
            )

        config_payload: dict[str, Any] | None = None
        if config is not None:
            config_payload = config
        elif config_path is not None:
            config_payload = json.loads(Path(config_path).read_text(encoding="utf-8"))

        artifacts: dict[str, Any] = {
            "input": self._artifact(image_path),
            "model": self._artifact(model_path),
            "config": {
                "sha256": sha256_hex(canonical_bytes(config_payload)) if config_payload else None,
                "content": config_payload,
            },
        }
        if output_path is not None:
            if not Path(output_path).is_file():
                raise FileNotFoundError(f"output file not found: {output_path}")
            artifacts["output"] = self._artifact(output_path)

        record: dict[str, Any] = {
            "record_id": f"tvp-{secrets.token_hex(8)}",
            "record_type": RECORD_TYPE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "artifacts": artifacts,
            "nonce": client_nonce or secrets.token_hex(16),
        }
        return self.ledger.append(record, self._signer)

    # ------------------------------------------------------------------
    # verification
    # ------------------------------------------------------------------

    def verify(self, presented: dict[str, Any], supplied_hashes: dict[str, str] | None) -> dict:
        checks: dict[str, bool] = {}
        details: dict[str, Any] = {}
        record_id = presented.get("record_id")

        required = ("record_id", "record_type", "timestamp", "nonce",
                    "artifacts", "verification_hash", "signature", "prev_hash")
        # note: prev_hash is legitimately None for the genesis record
        missing = [k for k in required if k not in presented]
        checks["structure_ok"] = not missing
        if missing:
            details["missing_fields"] = missing

        # record tampering: recompute the verification hash over the presented payload
        payload = {k: v for k, v in presented.items() if k not in ("verification_hash", "signature")}
        recomputed = sha256_hex(canonical_bytes(payload))
        checks["hash_ok"] = recomputed == presented.get("verification_hash")
        if not checks["hash_ok"]:
            details["recomputed_hash"] = recomputed

        # authenticity: Ed25519 signature over the verification hash
        try:
            signature = presented.get("signature") or {}
            verification_hash_bytes = bytes.fromhex(presented.get("verification_hash") or "")
            checks["signature_ok"] = (
                signature.get("algorithm") == "Ed25519"
                and signature.get("key_id") == self.keys.key_id
                and self.keys.verify(signature.get("value", ""), verification_hash_bytes)
            )
        except Exception:
            checks["signature_ok"] = False

        # replay attack: the nonce is bound to a different record
        nonce = presented.get("nonce")
        owner = self.ledger.nonce_owner(nonce) if nonce else None
        checks["replay_detected"] = bool(owner and record_id and owner != record_id)
        if checks["replay_detected"]:
            details["nonce_bound_to"] = owner

        # ledger presence / divergence from the stored copy
        stored = self.ledger.get(record_id) if record_id else None
        checks["known_to_ledger"] = stored is not None
        differs = stored is not None and presented != stored
        checks["differs_from_ledger"] = differs
        if differs:
            details["note"] = "presented record differs from the stored ledger entry"

        # output/input/model substitution against committed hashes
        substitution = False
        mismatches: list[dict] = []
        if supplied_hashes:
            mapping = {
                "input_sha256": "input",
                "model_sha256": "model",
                "config_sha256": "config",
                "output_sha256": "output",
            }
            artifacts = presented.get("artifacts") or {}
            for supplied_key, artifact_name in mapping.items():
                if supplied_key not in supplied_hashes:
                    continue
                committed = (artifacts.get(artifact_name) or {}).get("sha256")
                if committed != supplied_hashes[supplied_key]:
                    substitution = True
                    mismatches.append({
                        "artifact": artifact_name,
                        "committed": committed,
                        "presented": supplied_hashes[supplied_key],
                    })
        checks["artifacts_ok"] = not substitution
        if substitution:
            details["substitution_mismatches"] = mismatches

        # positive checks must hold; negative checks (replay / divergence) must not
        valid = (
            checks["structure_ok"]
            and checks["hash_ok"]
            and checks["signature_ok"]
            and checks["known_to_ledger"]
            and checks["artifacts_ok"]
            and not checks["replay_detected"]
            and not checks["differs_from_ledger"]
        )
        return {
            "record_id": record_id,
            "valid": valid,
            "checks": checks,
            "details": details,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # chain
    # ------------------------------------------------------------------

    def chain(self) -> dict:
        previous: str | None = None
        chain_ok = True
        issues: list[dict] = []
        for record in self.ledger.records:
            payload = {k: v for k, v in record.items() if k not in ("verification_hash", "signature")}
            expected = sha256_hex(canonical_bytes(payload))
            link_ok = record.get("prev_hash") == previous
            hash_ok = expected == record.get("verification_hash")
            signature = record.get("signature") or {}
            try:
                signature_ok = (
                    signature.get("key_id") == self.keys.key_id
                    and self.keys.verify(signature.get("value", ""),
                                         bytes.fromhex(record.get("verification_hash") or ""))
                )
            except Exception:
                signature_ok = False
            if not (link_ok and hash_ok and signature_ok):
                chain_ok = False
                issues.append({
                    "record_id": record.get("record_id"),
                    "link_ok": link_ok, "hash_ok": hash_ok, "signature_ok": signature_ok,
                })
            previous = record.get("verification_hash")
        return {
            "length": len(self.ledger.records),
            "chain_ok": chain_ok,
            "issues": issues[:50],
            "records": self.ledger.records,
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _artifact(self, path: Path) -> dict:
        path = Path(path)
        return {
            "sha256": sha256_file(path),
            "size": path.stat().st_size,
            "filename": path.name,
        }

    def _signer(self, data: bytes) -> tuple[str, str]:
        return self.keys.key_id, self.keys.sign(data)
