"""Uniform error envelope: {"error": {"code": ..., "message": ..., "details"?: ...}}.

Messages are written for end users. Stack traces never leave the server.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("contentfactory.errors")


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def not_found(entity: str = "Resource") -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, "not_found", f"{entity} not found.")


def forbidden(message: str = "You don't have access to this.") -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "forbidden", message)


def unauthorized(message: str = "Sign in to continue.", code: str = "unauthorized") -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, code, message)


def envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return {"error": body}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            envelope(exc.code, exc.message, exc.details),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields: dict[str, str] = {}
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query"))
            msg = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
            fields[loc or "request"] = msg
        return JSONResponse(
            envelope("validation_error", "Some fields need your attention.", {"fields": fields}),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(envelope(code, message), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            envelope("internal_error", "Something went wrong on our side. Please try again."),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
