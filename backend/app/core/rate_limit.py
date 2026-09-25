"""Redis fixed-window rate limiting, usable as a FastAPI dependency or directly."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, status

from app.core.errors import AppError
from app.core.redis import get_redis
from app.core.request_context import client_ip


async def hit(bucket: str, identifier: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Count one hit. Returns (allowed, retry_after_seconds)."""
    redis = get_redis()
    window = int(time.time()) // window_seconds
    key = f"rl:{bucket}:{identifier}:{window}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds + 1)
    if count > limit:
        retry_after = window_seconds - int(time.time()) % window_seconds
        return False, max(retry_after, 1)
    return True, 0


def too_many(retry_after: int, message: str | None = None) -> AppError:
    minutes = max(1, round(retry_after / 60))
    return AppError(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "rate_limited",
        message or f"Too many requests. Try again in {minutes} minute{'s' if minutes > 1 else ''}.",
        headers={"Retry-After": str(retry_after)},
    )


def rate_limit(
    bucket: str, limit: int, window_seconds: int
) -> Callable[[Request], Awaitable[None]]:
    """Per-IP limiter dependency."""

    async def _dep(request: Request) -> None:
        allowed, retry_after = await hit(bucket, client_ip(request), limit, window_seconds)
        if not allowed:
            raise too_many(retry_after)

    return _dep


def identifier_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()[:32]
