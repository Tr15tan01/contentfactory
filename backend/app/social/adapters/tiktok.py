"""TikTok Content Posting API (video, pulled from our storage URL).

Until TikTok audits the app, it only allows private (SELF_ONLY) posts; the adapter picks the
most public privacy level the creator's account currently offers and reports which it used.
"""

from __future__ import annotations

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

SCOPES = ["user.info.basic", "video.publish", "video.list"]
PRIVACY_PREFERENCE = [
    "PUBLIC_TO_EVERYONE",
    "MUTUAL_FOLLOW_FRIENDS",
    "FOLLOWER_OF_CREATOR",
    "SELF_ONLY",
]


class TikTokAdapter:
    provider = "tiktok"
    platforms = (Platform.TIKTOK,)
    label = "TikTok"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url="https://open.tiktokapis.com", timeout=60
        )

    def configured(self) -> bool:
        return bool(settings.TIKTOK_CLIENT_KEY and settings.TIKTOK_CLIENT_SECRET)

    def authorize_url(self, state: str, verifier: str, redirect_uri: str) -> str:
        q = urlencode(
            {
                "client_key": settings.TIKTOK_CLIENT_KEY,
                "scope": ",".join(SCOPES),
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "state": state,
                "code_challenge": challenge_for(verifier),
                "code_challenge_method": "S256",
            }
        )
        return f"https://www.tiktok.com/v2/auth/authorize/?{q}"

    async def _post(
        self,
        path: str,
        token: str | None = None,
        *,
        form: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            r = await self._client.post(path, data=form, json=json, headers=headers)
        except httpx.HTTPError as exc:
            raise SocialError(
                "TikTok couldn't be reached. Retrying.", code="unavailable", retryable=True
            ) from exc
        if r.status_code >= 400:
            raise http_error(r, "TikTok")
        body = r.json()
        err = body.get("error") or {}
        if isinstance(err, dict) and err.get("code") not in (None, "ok"):
            if err["code"] in ("access_token_invalid", "scope_not_authorized"):
                raise SocialError(
                    "TikTok access expired. Reconnect the account.", code="auth", needs_reauth=True
                )
            if err["code"] in ("rate_limit_exceeded", "internal_error"):
                raise SocialError("TikTok is busy. Retrying.", code="unavailable", retryable=True)
            raise SocialError(
                f"TikTok rejected the post: {err.get('message') or err['code']}", code="rejected"
            )
        return body

    def _tokens(self, data: dict[str, Any]) -> TokenSet:
        now = utcnow()
        return TokenSet(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=now + timedelta(seconds=int(data.get("expires_in", 86400))),
            refresh_expires_at=now + timedelta(seconds=int(data["refresh_expires_in"]))
            if data.get("refresh_expires_in")
            else None,
            scopes=str(data.get("scope", "")).split(","),
        )

    async def connect(self, code: str, verifier: str, redirect_uri: str) -> list[RemoteAccount]:
        data = await self._post(
            "/v2/oauth/token/",
            form={
                "client_key": settings.TIKTOK_CLIENT_KEY,
                "client_secret": settings.TIKTOK_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            },
        )
        token = self._tokens(data)
        try:
            r = await self._client.get(
                "/v2/user/info/",
                params={"fields": "open_id,display_name,avatar_url,username"},
                headers={"Authorization": f"Bearer {token.access_token}"},
            )
        except httpx.HTTPError as exc:
            raise SocialError(
                "TikTok couldn't be reached.", code="unavailable", retryable=True
            ) from exc
        user = (r.json().get("data") or {}).get("user") or {}
        return [
            RemoteAccount(
                Platform.TIKTOK,
                user.get("open_id") or data.get("open_id"),
                user.get("display_name"),
                user.get("username"),
                user.get("avatar_url"),
                token,
            )
        ]

    async def refresh(self, token: TokenSet) -> TokenSet | None:
        if not token.refresh_token:
            return None
        data = await self._post(
            "/v2/oauth/token/",
            form={
                "client_key": settings.TIKTOK_CLIENT_KEY,
                "client_secret": settings.TIKTOK_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
            },
        )
        return self._tokens(data)

    def validate(self, req: PublishRequest) -> list[str]:
        if req.content_type not in (ContentType.REEL, ContentType.SHORT, ContentType.VIDEO):
            return ["TikTok publishing supports videos only."]
        if not any(m.kind == "video" for m in req.media):
            return ["TikTok posts need a video."]
        return []

    async def publish(
        self, account_id: str, token: TokenSet, req: PublishRequest, state: dict[str, Any]
    ) -> PublishResult:
        tok = token.access_token
        if not state.get("publish_id"):
            info = (await self._post("/v2/post/publish/creator_info/query/", tok, json={})).get(
                "data"
            ) or {}
            options = info.get("privacy_level_options") or ["SELF_ONLY"]
            privacy = next((p for p in PRIVACY_PREFERENCE if p in options), options[0])
            video = next(m for m in req.media if m.kind == "video")
            data = await self._post(
                "/v2/post/publish/video/init/",
                tok,
                json={
                    "post_info": {"title": req.caption[:2200], "privacy_level": privacy},
                    "source_info": {"source": "PULL_FROM_URL", "video_url": video.url},
                },
            )
            state["publish_id"] = data["data"]["publish_id"]
            state["privacy_level"] = privacy
            state["username"] = info.get("creator_username")
        status = (
            await self._post(
                "/v2/post/publish/status/fetch/", tok, json={"publish_id": state["publish_id"]}
            )
        ).get("data") or {}
        s = status.get("status")
        if s == "PUBLISH_COMPLETE":
            ids = (
                status.get("publicaly_available_post_id")
                or status.get("publicly_available_post_id")
                or []
            )
            post_id = str(ids[0]) if ids else str(state["publish_id"])
            url = (
                f"https://www.tiktok.com/@{state.get('username')}/video/{ids[0]}"
                if ids and state.get("username")
                else None
            )
            return PublishResult(post_id, url, {"privacy_level": state.get("privacy_level")})
        if s == "FAILED":
            state.pop("publish_id", None)
            reason = status.get("fail_reason") or "no reason given"
            raise SocialError(f"TikTok couldn't publish the video: {reason}", code="rejected")
        raise SocialError(
            "TikTok is still processing the video.", code="processing", processing=True
        )

    async def fetch_metrics(
        self,
        platform: Platform,
        account_id: str,
        token: TokenSet,
        post_id: str,
        content_type: ContentType,
    ) -> dict[str, float]:
        data = await self._post(
            "/v2/video/query/?fields=id,view_count,like_count,comment_count,share_count",
            token.access_token,
            json={"filters": {"video_ids": [post_id]}},
        )
        videos = (data.get("data") or {}).get("videos") or []
        if not videos:
            return {}
        v = videos[0]
        mapping = {
            "view_count": "views",
            "like_count": "likes",
            "comment_count": "comments",
            "share_count": "shares",
        }
        return {
            name: float(v[key])
            for key, name in mapping.items()
            if isinstance(v.get(key), int | float)
        }
