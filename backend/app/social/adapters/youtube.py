"""YouTube Data API v3: resumable upload of Shorts and videos from our storage.

Google keeps uploads from unverified apps private until the app passes verification.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.security import utcnow
from app.models.enums import ContentType, Platform
from app.social.base import (
    PublishRequest,
    PublishResult,
    RemoteAccount,
    SocialError,
    TokenSet,
    challenge_for,
    http_error,
)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class YouTubeAdapter:
    provider = "youtube"
    platforms = (Platform.YOUTUBE,)
    label = "YouTube"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(60, read=600))

    def configured(self) -> bool:
        return bool(
            settings.YOUTUBE_ENABLED and settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET
        )

    def authorize_url(self, state: str, verifier: str, redirect_uri: str) -> str:
        q = urlencode(
            {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
                "code_challenge": challenge_for(verifier),
                "code_challenge_method": "S256",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{q}"

    async def _token(self, form: dict[str, str]) -> TokenSet:
        try:
            r = await self._client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    **form,
                },
            )
        except httpx.HTTPError as exc:
            raise SocialError(
                "Google couldn't be reached.", code="unavailable", retryable=True
            ) from exc
        if r.status_code == 400 and r.json().get("error") == "invalid_grant":
            raise SocialError(
                "Google access was revoked or expired. Reconnect YouTube.",
                code="auth",
                needs_reauth=True,
            )
        if r.status_code >= 400:
            raise http_error(r, "Google")
        d = r.json()
        return TokenSet(
            access_token=d["access_token"],
            refresh_token=d.get("refresh_token"),
            expires_at=utcnow() + timedelta(seconds=int(d.get("expires_in", 3600))),
            scopes=str(d.get("scope", "")).split(),
        )

    async def connect(self, code: str, verifier: str, redirect_uri: str) -> list[RemoteAccount]:
        token = await self._token(
            {
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            }
        )
        if not token.refresh_token:
            raise SocialError(
                "Google didn't grant offline access. Try connecting again.", code="rejected"
            )
        r = await self._client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {token.access_token}"},
        )
        if r.status_code >= 400:
            raise http_error(r, "YouTube")
        items = r.json().get("items") or []
        if not items:
            raise SocialError("This Google account has no YouTube channel.", code="no_channel")
        return [
            RemoteAccount(
                Platform.YOUTUBE,
                c["id"],
                c["snippet"].get("title"),
                c["snippet"].get("customUrl"),
                ((c["snippet"].get("thumbnails") or {}).get("default") or {}).get("url"),
                token,
            )
            for c in items
        ]

    async def refresh(self, token: TokenSet) -> TokenSet | None:
        if not token.refresh_token:
            return None
        fresh = await self._token(
            {"grant_type": "refresh_token", "refresh_token": token.refresh_token}
        )
        fresh.refresh_token = fresh.refresh_token or token.refresh_token  # Google often omits it
        return fresh

    def validate(self, req: PublishRequest) -> list[str]:
        video = next((m for m in req.media if m.kind == "video"), None)
        if not video:
            return ["YouTube posts need a video."]
        if (
            req.content_type is ContentType.SHORT
            and video.duration_seconds
            and video.duration_seconds > 180
        ):
            return ["Shorts can be up to 3 minutes long."]
        return []

    async def publish(
        self, account_id: str, token: TokenSet, req: PublishRequest, state: dict[str, Any]
    ) -> PublishResult:
        video = next(m for m in req.media if m.kind == "video")
        if video.open is None:
            raise SocialError("The video file isn't available for upload.", code="media_missing")
        auth = {"Authorization": f"Bearer {token.access_token}"}
        description = req.caption + (
            "\n\n#Shorts"
            if req.content_type is ContentType.SHORT and "#shorts" not in req.caption.lower()
            else ""
        )
        meta = {
            "snippet": {
                "title": req.title[:100] or "New video",
                "description": description[:5000],
                "categoryId": "22",
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }
        try:
            init = await self._client.post(
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    **auth,
                    "Content-Type": "application/json",
                    "X-Upload-Content-Type": video.mime_type,
                    "X-Upload-Content-Length": str(video.size_bytes),
                },
                content=json.dumps(meta),
            )
            if init.status_code >= 400:
                raise http_error(init, "YouTube")
            upload = await self._client.put(
                init.headers["location"],
                content=video.open(),
                headers={
                    **auth,
                    "Content-Type": video.mime_type,
                    "Content-Length": str(video.size_bytes),
                },
            )
        except httpx.HTTPError as exc:
            raise SocialError(
                "The upload to YouTube was interrupted. Retrying.",
                code="unavailable",
                retryable=True,
            ) from exc
        if upload.status_code >= 400:
            raise http_error(upload, "YouTube")
        vid = upload.json()["id"]
        url = (
            f"https://www.youtube.com/shorts/{vid}"
            if req.content_type is ContentType.SHORT
            else f"https://www.youtube.com/watch?v={vid}"
        )
        return PublishResult(
            vid, url, {"privacy_status": upload.json().get("status", {}).get("privacyStatus")}
        )

    async def fetch_metrics(
        self,
        platform: Platform,
        account_id: str,
        token: TokenSet,
        post_id: str,
        content_type: ContentType,
    ) -> dict[str, float]:
        try:
            r = await self._client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "statistics", "id": post_id},
                headers={"Authorization": f"Bearer {token.access_token}"},
            )
        except httpx.HTTPError as exc:
            raise SocialError(
                "YouTube couldn't be reached.", code="unavailable", retryable=True
            ) from exc
        if r.status_code >= 400:
            raise http_error(r, "YouTube")
        items = r.json().get("items") or []
        if not items:
            return {}
        stats = items[0].get("statistics") or {}
        mapping = {"viewCount": "views", "likeCount": "likes", "commentCount": "comments"}
        return {
            name: float(stats[key])
            for key, name in mapping.items()
            if str(stats.get(key, "")).isdigit()
        }
