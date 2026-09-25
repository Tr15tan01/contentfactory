"""Google OAuth 2.0 (authorization code + PKCE). Enabled with AUTH_GOOGLE_ENABLED=1."""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import urlencode

import httpx

from app.auth.service import GoogleProfile
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import generate_token, sign_value, unsign_value

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
STATE_COOKIE = "cf_oauth_google"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def safe_next(path: str | None) -> str:
    """Only allow same-site relative redirects after login."""
    if path and path.startswith("/") and not path.startswith("//") and "\\" not in path:
        return path[:300]
    return "/dashboard"


def start(next_path: str | None) -> tuple[str, str]:
    """Returns (authorize_url, signed_state_cookie_value)."""
    state = generate_token(16)
    verifier = generate_token(48)
    challenge = _b64(hashlib.sha256(verifier.encode()).digest())
    cookie = sign_value(
        _b64(json.dumps({"s": state, "v": verifier, "n": safe_next(next_path)}).encode())
    )
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}", cookie


def read_state(cookie: str | None, state: str | None) -> tuple[str, str]:
    """Validate the callback state against the signed cookie. Returns (verifier, next_path)."""
    raw = unsign_value(cookie or "")
    if not raw or not state:
        raise AppError(400, "oauth_state_invalid", "Google sign-in expired. Please try again.")
    padded = raw + "=" * (-len(raw) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded))
    if data.get("s") != state:
        raise AppError(400, "oauth_state_invalid", "Google sign-in expired. Please try again.")
    return data["v"], safe_next(data.get("n"))


async def fetch_profile(code: str, verifier: str) -> GoogleProfile:
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_redirect_uri,
            },
        )
        if token_resp.status_code != 200:
            raise AppError(400, "oauth_exchange_failed", "Google sign-in failed. Please try again.")
        access_token = token_resp.json()["access_token"]
        info = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if info.status_code != 200:
            raise AppError(400, "oauth_exchange_failed", "Google sign-in failed. Please try again.")
        data = info.json()
    return GoogleProfile(
        sub=data["sub"],
        email=data["email"],
        email_verified=bool(data.get("email_verified")),
        name=data.get("name"),
        picture=data.get("picture"),
    )
