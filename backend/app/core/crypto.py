"""Envelope for secrets stored at rest (social OAuth tokens, etc.).

Uses MultiFernet so keys can be rotated: new data is encrypted with the first key,
old data remains readable with any listed key. Run `rotate()` in a job to re-encrypt.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings


@lru_cache
def _fernet() -> MultiFernet:
    keys = [k.strip() for k in settings.ENCRYPTION_KEYS.split(",") if k.strip()]
    if not keys:
        if settings.is_production:
            raise RuntimeError("ENCRYPTION_KEYS is not configured")
        # Development fallback derived from SESSION_SECRET, so the API and workers share it
        # (a random per-process key would make tokens unreadable across processes).
        # Production refuses to start without ENCRYPTION_KEYS.
        digest = hashlib.sha256(
            b"contentfactory-dev-encryption:" + settings.SESSION_SECRET.encode()
        ).digest()
        keys = [base64.urlsafe_b64encode(digest).decode()]
    return MultiFernet([Fernet(k.encode()) for k in keys])


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt(ciphertext: bytes) -> str:
    return _fernet().decrypt(ciphertext).decode()


def rotate(ciphertext: bytes) -> bytes:
    return _fernet().rotate(ciphertext)


__all__ = ["InvalidToken", "decrypt", "encrypt", "rotate"]
