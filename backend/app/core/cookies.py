from __future__ import annotations

from datetime import timedelta

from fastapi import Response

from app.core.config import settings
from app.core.csrf import CSRF_COOKIE, new_csrf_token

ACCESS_COOKIE = "cf_access"
REFRESH_COOKIE = "cf_refresh"
REFRESH_COOKIE_PATH = f"{settings.API_PREFIX}/auth"
# Non-sensitive hint ("1") that lives as long as the refresh cookie and is visible on every
# path. The Next.js proxy uses it to redirect signed-out visitors before rendering app pages;
# it grants nothing by itself — every API call is still authorised by cf_access.
SIGNED_IN_COOKIE = "cf_signed_in"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=int(timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES).total_seconds()),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=int(timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS).total_seconds()),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        domain=settings.COOKIE_DOMAIN,
        path=REFRESH_COOKIE_PATH,
    )
    response.set_cookie(
        SIGNED_IN_COOKIE,
        "1",
        max_age=int(timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS).total_seconds()),
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    # Rotate the CSRF token whenever the auth context changes.
    set_csrf_cookie(response)


def set_csrf_cookie(response: Response, token: str | None = None) -> str:
    token = token or new_csrf_token()
    response.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=int(timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS).total_seconds()),
        httponly=False,  # must be readable by the frontend to echo in a header
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )
    return token


def clear_auth_cookies(response: Response) -> None:
    for name, path, httponly in (
        (ACCESS_COOKIE, "/", True),
        (REFRESH_COOKIE, REFRESH_COOKIE_PATH, True),
        (SIGNED_IN_COOKIE, "/", False),
    ):
        response.delete_cookie(
            name,
            path=path,
            domain=settings.COOKIE_DOMAIN,
            secure=settings.COOKIE_SECURE,
            httponly=httponly,
        )
