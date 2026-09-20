"""Append-only, hash-chained provenance ledger persisted as JSONL.

Each record carries ``prev_hash`` (the previous record's verification hash) and
a ``verification_hash`` = SHA-256 over the canonical serialization of the
record payload (everything except ``verification_hash`` and ``signature``).
The ledger file is append-only; updates and deletions are refused.
"""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path
from typing import Callable

from app.core.logging import get_logger
from app.services.hashing import canonical_bytes, sha256_hex

log = get_logger(__name__)

RESERVED_FIELDS = ("verification_hash", "signature")


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self.records: list[dict] = []
        self.by_id: dict[str, dict] = {}
        self._nonce_owner: dict[str, str] = {}
        self.tail: str | None = None
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    log.error("ledger line unparsable — chain integrity compromised: %s", exc)
                    continue
                self.records.append(record)
                self.by_id[record.get("record_id")] = record
                if record.get("nonce"):
                    self._nonce_owner[record["nonce"]] = record["record_id"]
                self.tail = record.get("verification_hash")
        log.info("ledger loaded: %d records (tail %s)", len(self.records), self.tail)

    def append(self, record: dict, signer: Callable[[bytes], tuple[str, str]]) -> dict:
        """Assign prev_hash, compute the verification hash, sign and append.

        ``signer(data) -> (key_id, signature)`` is invoked on the verification
        hash bytes. The ledger file is strictly append-only.
        """
        with self._lock:
            entry = dict(record)
            entry["prev_hash"] = self.tail
            payload = {k: v for k, v in entry.items() if k not in RESERVED_FIELDS}
            verification_hash = sha256_hex(canonical_bytes(payload))
            key_id, signature = signer(bytes.fromhex(verification_hash))
            entry["verification_hash"] = verification_hash
            entry["signature"] = {"algorithm": "Ed25519", "key_id": key_id, "value": signature}

            self.records.append(entry)
            self.by_id[entry["record_id"]] = entry
            if entry.get("nonce"):
                self._nonce_owner[entry["nonce"]] = entry["record_id"]
            self.tail = verification_hash

            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
            log.info("record %s appended (nonce %s)", entry["record_id"], entry.get("nonce"))
            return entry

    def get(self, record_id: str) -> dict | None:
        return self.by_id.get(record_id)

    def nonce_owner(self, nonce: str) -> str | None:
        return self._nonce_owner.get(nonce)

    def records_chain_integrity(self) -> tuple[bool, list[dict]]:
        """Walk the in-memory chain: prev-hash links and per-record hash recomputation."""
        previous: str | None = None
        ok = True
        issues: list[dict] = []
        for record in self.records:
            payload = {k: v for k, v in record.items() if k not in RESERVED_FIELDS}
            expected = sha256_hex(canonical_bytes(payload))
            link_ok = record.get("prev_hash") == previous
            hash_ok = expected == record.get("verification_hash")
            if not (link_ok and hash_ok):
                ok = False
                issues.append({
                    "record_id": record.get("record_id"),
                    "link_ok": link_ok,
                    "hash_ok": hash_ok,
                })
            previous = record.get("verification_hash")
        return ok, issues


@lru_cache
def get_ledger() -> Ledger:
    from app.core.config import get_settings

    return Ledger(get_settings().resolved_ledger_path)
