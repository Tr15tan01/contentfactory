"""Password hashing, opaque token generation and access-token (JWT) handling."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

# Argon2id, RFC 9106 "low memory" profile (t=3, m=64 MiB, p=4) — argon2-cffi's default.
_hasher = PasswordHasher()
# Pre-computed hash used to keep timing uniform when an account does not exist.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "contentfactory"
JWT_AUDIENCE = "contentfactory-app"


def utcnow() -> datetime:
    return datetime.now(UTC)


# ----------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time verification; also burns a hash when there is no stored hash."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_problems(password: str, email: str | None = None) -> list[str]:
    problems: list[str] = []
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        problems.append(f"Use at least {settings.PASSWORD_MIN_LENGTH} characters.")
    if len(password) > 128:
        problems.append("Use at most 128 characters.")
    if len(set(password)) < 4:
        problems.append("Use a less repetitive password.")
    if email and email.split("@")[0].lower() in password.lower() and len(email.split("@")[0]) > 3:
        problems.append("Don't include your email address in your password.")
    return problems


# ----------------------------------------------------------------------------- opaque tokens
def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Keyed hash for storing opaque tokens (refresh, reset, verification).

    Tokens are high-entropy, so HMAC-SHA256 with a server-side pepper is sufficient and
    lets us look them up by hash with a unique index.
    """
    return hmac.new(settings.SESSION_SECRET.encode(), token.encode(), hashlib.sha256).hexdigest()


def sign_value(value: str) -> str:
    sig = hmac.new(settings.SESSION_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{sig[:32]}"


def unsign_value(signed: str) -> str | None:
    value, _, sig = signed.rpartition(".")
    if not value or not sig:
        return None
    expected = sign_value(value).rpartition(".")[2]
    return value if hmac.compare_digest(sig, expected) else None


# ----------------------------------------------------------------------------- JWT
def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, datetime]:
    now = utcnow()
    expires = now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM), expires


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "sid"]},
        )
    except jwt.PyJWTError:
        return None
    return payload if payload.get("typ") == "access" else None
