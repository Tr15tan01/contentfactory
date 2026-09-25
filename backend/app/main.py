from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.router import api_router
from app.core.config import settings
from app.core.csrf import CSRF_HEADER, CSRFMiddleware
from app.core.database import engine
from app.core.errors import register_error_handlers

logging.basicConfig(level=settings.LOG_LEVEL)

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"cache-control", b"no-store"),
]


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def _send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {name.lower() for name, _ in headers}
                # Routes may opt into caching (signed media URLs); everything else is no-store.
                headers.extend(h for h in SECURITY_HEADERS if h[0] not in present)
            await send(message)

        await self.app(scope, receive, _send if scope["type"] == "http" else send)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="ContentFactory API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    register_error_handlers(app)
    # Order: outermost first at runtime is the *last* added.
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["content-type", CSRF_HEADER],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(api_router, prefix=settings.API_PREFIX)
    return app


app = create_app()
