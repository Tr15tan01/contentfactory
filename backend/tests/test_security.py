from __future__ import annotations

import uuid
from datetime import timedelta

import jwt

from app.core import crypto
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    sign_value,
    unsign_value,
    utcnow,
    verify_password,
)


def test_argon2id_hashing() -> None:
    h = hash_password("correct-horse-battery")
    assert h.startswith("$argon2id$")
    assert verify_password("correct-horse-battery", h)
    assert not verify_password("wrong", h)
    assert not verify_password("anything", None)


def test_token_hash_is_keyed_and_stable() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")
    assert len(hash_token("abc")) == 64


def test_access_token_roundtrip_and_tamper() -> None:
    uid, sid = uuid.uuid4(), uuid.uuid4()
    token, _ = create_access_token(uid, sid)
    payload = decode_access_token(token)
    assert payload and payload["sub"] == str(uid) and payload["sid"] == str(sid)
    assert decode_access_token(token[:-2] + "xx") is None
    forged = jwt.encode({**payload}, "not-the-secret-0123456789abcdef0123456789", algorithm="HS256")
    assert decode_access_token(forged) is None


def test_expired_access_token_rejected() -> None:
    now = utcnow()
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "sid": str(uuid.uuid4()),
            "typ": "access",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
            "iss": "contentfactory",
            "aud": "contentfactory-app",
        },
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    assert decode_access_token(token) is None


def test_signed_values() -> None:
    signed = sign_value("hello")
    assert unsign_value(signed) == "hello"
    assert unsign_value(signed[:-1] + ("0" if signed[-1] != "0" else "1")) is None


def test_social_token_encryption_roundtrip() -> None:
    blob = crypto.encrypt("EAAB-secret-token")
    assert b"EAAB" not in blob
    assert crypto.decrypt(blob) == "EAAB-secret-token"


def test_dev_encryption_key_is_shared_across_processes() -> None:
    """Without ENCRYPTION_KEYS (development), every process must derive the same key."""
    from app.core import crypto

    token = crypto.encrypt("page-token")
    crypto._fernet.cache_clear()  # simulate a fresh process (e.g. the worker)
    assert crypto.decrypt(token) == "page-token"
