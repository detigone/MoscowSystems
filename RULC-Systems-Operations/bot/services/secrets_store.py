from __future__ import annotations

import base64
import hashlib
import logging

logger = logging.getLogger(__name__)

_PREFIX = "enc:"

try:
    from cryptography.fernet import Fernet, InvalidToken

    _HAS_FERNET = True
except ImportError:
    Fernet = None  # type: ignore[misc, assignment]
    InvalidToken = Exception  # type: ignore[misc, assignment]
    _HAS_FERNET = False


def _derive_key(raw: str) -> bytes:
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class SecretsStore:
    """Encrypt sensitive DB fields at rest (ER:LC keys, webhook URLs)."""

    def __init__(self, key: str | None) -> None:
        self._fernet: Fernet | None = None
        if not key:
            return
        if not _HAS_FERNET:
            logger.warning(
                "SECRETS_KEY is set but cryptography is not installed — secrets stay plaintext"
            )
            return
        try:
            self._fernet = Fernet(_derive_key(key.strip()))
        except Exception:
            logger.exception("Invalid SECRETS_KEY — encryption disabled")

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def seal(self, value: str) -> str:
        if not value or not self._fernet:
            return value
        token = self._fernet.encrypt(value.encode("utf-8")).decode("ascii")
        return f"{_PREFIX}{token}"

    def open(self, value: str) -> str:
        if not value:
            return value
        if not value.startswith(_PREFIX):
            return value
        if not self._fernet:
            logger.warning("Encrypted secret in DB but SECRETS_KEY unavailable")
            return value
        try:
            return self._fernet.decrypt(value[len(_PREFIX) :].encode("ascii")).decode("utf-8")
        except InvalidToken:
            logger.exception("Failed to decrypt secret — check SECRETS_KEY")
            return value
