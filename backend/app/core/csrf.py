"""CSRF protection: signed double-submit cookie + Origin check for unsafe methods.

The browser receives a readable `cf_csrf` cookie (signed with SESSION_SECRET). Every
state-changing request must echo it in the `X-CSRF-Token` header. Auth cookies are also
SameSite, so this is defence in depth rather than the only barrier.
"""

from __future__ import annotations

import hmac
import json

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.errors import envelope
from app.core.security import generate_token, sign_value, unsign_value

CSRF_COOKIE = "cf_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
# Server-to-server endpoints authenticated by signatures instead of cookies.
EXEMPT_PREFIXES = (
    f"{settings.API_PREFIX}/billing/webhooks/",
    f"{settings.API_PREFIX}/health",
    # Authorised by a signed, single-purpose capability token instead of cookies.
    f"{settings.API_PREFIX}/storage/local/",
)


def new_csrf_token() -> str:
    return sign_value(generate_token(24))


def _cookie(scope: Scope, name: str) -> str | None:
    for key, value in scope.get("headers", []):
        if key == b"cookie":
            for part in value.decode("latin-1").split(";"):
                k, _, v = part.strip().partition("=")
                if k == name:
                    return v
    return None


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return None


class CSRFMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.allowed_origins = {o.rstrip("/") for o in [*settings.CORS_ORIGINS, settings.APP_URL]}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        if path.startswith(EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return

        origin = _header(scope, b"origin")
        if origin and origin.rstrip("/") not in self.allowed_origins:
            await self._reject(send, "Request origin is not allowed.")
            return

        cookie = _cookie(scope, CSRF_COOKIE)
        header = _header(scope, CSRF_HEADER.encode())
        if (
            not cookie
            or not header
            or not hmac.compare_digest(cookie, header)
            or unsign_value(cookie) is None
        ):
            await self._reject(send, "Your session security token expired. Refresh the page.")
            return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, message: str) -> None:
        body = json.dumps(envelope("csrf_failed", message)).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": body})
