"""Ed25519 signing keys, generated once and persisted offline."""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.logging import get_logger

log = get_logger(__name__)


class KeyManager:
    """Loads (or first-run generates) the site signing key.

    The private key never leaves the engine; verification uses the paired
    public key. In production the key is injected from the site secret store
    (HSM / secret file) via TVP_SIGNING_KEY_PATH.
    """

    def __init__(self, key_path: Path) -> None:
        self.key_path = Path(key_path)
        if self.key_path.exists():
            self._private = serialization.load_pem_private_key(
                self.key_path.read_bytes(), password=None
            )
            log.info("loaded signing key from %s", self.key_path)
        else:
            self._private = Ed25519PrivateKey.generate()
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            self.key_path.write_bytes(
                self._private.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                )
            )
            log.info("generated new Ed25519 signing key at %s", self.key_path)

        public_raw = self._private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.key_id = hashlib.sha256(public_raw).hexdigest()[:16]
        self.public_key_hex = public_raw.hex()

    def sign(self, data: bytes) -> str:
        return base64.b64encode(self._private.sign(data)).decode("ascii")

    def verify(self, signature_b64: str, data: bytes) -> bool:
        try:
            self._private.public_key().verify(base64.b64decode(signature_b64), data)
            return True
        except Exception:
            return False


@lru_cache
def get_key_manager() -> KeyManager:
    from app.core.config import get_settings

    return KeyManager(get_settings().resolved_signing_key_path)
