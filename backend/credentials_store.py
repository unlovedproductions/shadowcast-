"""Encrypted credential storage for OAuth tokens and platform sessions."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    Fernet = None
    InvalidToken = Exception

# Outside OUTPUT_BASE so /api/download cannot serve tokens as job files.
DEFAULT_STORE_DIR = Path(__file__).parent / "credentials"
LEGACY_STORE_DIR = Path(__file__).parent / "output" / "credentials"
_DEV_FALLBACK_KEY = "shadowcast-dev-key"


def _derive_key(secret: str) -> bytes:
    salt = b"shadowcast-credentials-v1"
    derived = hashlib.scrypt(
        secret.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return base64.urlsafe_b64encode(derived)


def _resolve_encryption_secret(encryption_key: str | None) -> str:
    secret = (
        encryption_key
        or os.getenv("CREDENTIALS_ENCRYPTION_KEY")
        or os.getenv("INTERNAL_SERVICE_SECRET")
        or ""
    ).strip()
    if secret:
        return secret
    allow_dev = os.getenv("SHADOWCAST_ALLOW_DEV_CREDENTIALS", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if allow_dev:
        return _DEV_FALLBACK_KEY
    raise RuntimeError(
        "CREDENTIALS_ENCRYPTION_KEY or INTERNAL_SERVICE_SECRET is required. "
        "Set SHADOWCAST_ALLOW_DEV_CREDENTIALS=1 only for throwaway local use."
    )


def _migrate_legacy_store(dest: Path) -> None:
    if dest.exists() and any(dest.glob("*.json")):
        return
    if not LEGACY_STORE_DIR.is_dir():
        return
    legacy_files = list(LEGACY_STORE_DIR.glob("*.json"))
    if not legacy_files:
        return
    dest.mkdir(parents=True, exist_ok=True)
    for src in legacy_files:
        target = dest / src.name
        if not target.exists():
            shutil.copy2(src, target)


class CredentialsStore:
    def __init__(self, store_dir: str | Path | None = None, encryption_key: str | None = None):
        configured = store_dir or os.getenv("CREDENTIALS_STORE_DIR")
        self.store_dir = Path(configured) if configured else DEFAULT_STORE_DIR
        if not configured:
            _migrate_legacy_store(self.store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        secret = _resolve_encryption_secret(encryption_key)
        self._secret = secret
        self._fernet = Fernet(_derive_key(secret)) if Fernet else None

    def _path(self, platform: str) -> Path:
        safe = platform.replace("/", "_")
        return self.store_dir / f"{safe}.json"

    def _encode(self, raw: bytes) -> bytes:
        if self._fernet:
            return self._fernet.encrypt(raw)
        return base64.b64encode(raw)

    def _decode(self, data: bytes) -> bytes:
        if self._fernet:
            return self._fernet.decrypt(data)
        return base64.b64decode(data)

    def save(self, platform: str, data: dict[str, Any]) -> None:
        payload = {
            "platform": platform,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        raw = json.dumps(payload).encode("utf-8")
        self._path(platform).write_bytes(self._encode(raw))

    def load(self, platform: str) -> dict[str, Any] | None:
        path = self._path(platform)
        if not path.exists():
            return None
        try:
            decrypted = self._decode(path.read_bytes())
            payload = json.loads(decrypted.decode("utf-8"))
            return payload.get("data")
        except (InvalidToken, json.JSONDecodeError, KeyError, ValueError):
            return None

    def delete(self, platform: str) -> bool:
        path = self._path(platform)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_connected(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for path in self.store_dir.glob("*.json"):
            platform = path.stem
            result[platform] = self.load(platform) is not None
        return result
