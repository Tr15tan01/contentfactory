"""Instagram (professional accounts) and Facebook Pages via the Meta Graph API."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.security import utcnow
from app.models.enums import ContentType, Platform
from app.social.base import PublishRequest, PublishResult, RemoteAccount, SocialError, TokenSet

SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "business_management",
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_insights",
]
RATE_LIMIT_CODES = {4, 17, 32, 613}


def _insight_values(data: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in data.get("data", []):
        value = (
            row.get("total_value", {}).get("value")
            if "total_value" in row
            else (row.get("values") or [{}])[-1].get("value")
        )
        if isinstance(value, int | float):
            out[row["name"]] = float(value)
    return out


class MetaAdapter:
    provider = "meta"
    platforms = (Platform.INSTAGRAM, Platform.FACEBOOK)
    label = "Instagram and Facebook"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=settings.META_GRAPH_BASE_URL or "https://graph.facebook.com", timeout=60
        )

    @property
    def _v(self) -> str:
        return settings.META_GRAPH_VERSION

    def configured(self) -> bool:
        return bool(settings.META_CLIENT_ID and settings.META_CLIENT_SECRET)

    def authorize_url(self, state: str, verifier: str, redirect_uri: str) -> str:
        q = urlencode(
            {
                "client_id": settings.META_CLIENT_ID,
                "redirect_uri": redirect_uri,
                "state": state,
                "response_type": "code",
                "scope": ",".join(SCOPES),
            }
        )
        host = settings.META_DIALOG_BASE_URL or "https://www.facebook.com"
        return f"{host}/{self._v}/dialog/oauth?{q}"

    async def _graph(self, method: str, path: str, **params: Any) -> dict[str, Any]:
        try:
            r = await self._client.request(
                method,
                f"/{self._v}/{path.lstrip('/')}",
                params=params if method == "GET" else None,
                data=None if method == "GET" else params,
            )
        except httpx.HTTPError as exc:
            raise SocialError(
                "Meta couldn't be reached. Retrying.", code="unavailable", retryable=True
            ) from exc
        data = r.json() if r.content else {}
        err = data.get("error") if isinstance(data, dict) else None
        if err or r.status_code >= 400:
            code = int((err or {}).get("code") or 0)
            msg = (err or {}).get("message") or f"Meta returned {r.status_code}."
            if code == 190 or r.status_code == 401:
                raise SocialError(
                    "Meta access expired or was removed. Reconnect the account.",
                    code="auth",
                    needs_reauth=True,
                )
            if code in RATE_LIMIT_CODES or r.status_code >= 500:
                raise SocialError(
                    "Meta rate limit or outage. Retrying.", code="unavailable", retryable=True
                )
            raise SocialError(f"Meta rejected the post: {msg}", code="rejected")
        return data

    async def connect(self, code: str, verifier: str, redirect_uri: str) -> list[RemoteAccount]:
        short = await self._graph(
            "GET",
            "oauth/access_token",
            client_id=settings.META_CLIENT_ID,
            client_secret=settings.META_CLIENT_SECRET,
            redirect_uri=redirect_uri,
            code=code,
        )
        long = await self._graph(
            "GET",
            "oauth/access_token",
            grant_type="fb_exchange_token",
            client_id=settings.META_CLIENT_ID,
            client_secret=settings.META_CLIENT_SECRET,
            fb_exchange_token=short["access_token"],
        )
        pages = await self._graph(
            "GET",
            "me/accounts",
            access_token=long["access_token"],
            limit="50",
            fields="id,name,access_token,picture{url},instagram_business_account{id,username,profile_picture_url}",
        )
        accounts: list[RemoteAccount] = []
        for page in pages.get("data", []):
            # Page tokens obtained from a long-lived user token don't expire.
            token = TokenSet(access_token=page["access_token"], scopes=SCOPES)
            accounts.append(
                RemoteAccount(
                    Platform.FACEBOOK,
                    page["id"],
                    page.get("name"),
                    None,
                    (page.get("picture") or {}).get("data", {}).get("url"),
                    token,
                )
            )
            ig = page.get("instagram_business_account")
            if ig:
                accounts.append(
                    RemoteAccount(
                        Platform.INSTAGRAM,
                        ig["id"],
                        ig.get("username"),
                        ig.get("username"),
                        ig.get("profile_picture_url"),
                        token,
                        {"page_id": page["id"]},
                    )
                )
        return accounts

    async def refresh(self, token: TokenSet) -> TokenSet | None:
        return None  # page tokens are long-lived; an invalid one surfaces as needs_reauth

    def validate(self, req: PublishRequest) -> list[str]:
        images = [m for m in req.media if m.kind == "image"]
        videos = [m for m in req.media if m.kind == "video"]
        problems: list[str] = []
        if req.platform is Platform.INSTAGRAM:
            if not req.media:
                problems.append("Instagram posts need a photo or video.")
            if req.content_type is ContentType.REEL and not videos:
                problems.append("Reels need a video.")
            if req.content_type is ContentType.CAROUSEL and not 2 <= len(req.media) <= 10:
                problems.append("Instagram carousels need 2 to 10 photos or videos.")
            if req.content_type is ContentType.POST and len(req.media) > 1:
                problems.append("Use a carousel for more than one photo.")
            for m in images:
                if m.mime_type not in ("image/jpeg",):
                    problems.append(
                        "Instagram only accepts JPEG photos through its API. Save it as JPEG."
                    )
                    break
        elif req.content_type in (ContentType.REEL, ContentType.VIDEO) and not videos:
            problems.append("This format needs a video.")
        return problems

    async def publish(
        self, account_id: str, token: TokenSet, req: PublishRequest, state: dict[str, Any]
    ) -> PublishResult:
        if req.platform is Platform.FACEBOOK:
            return await self._publish_facebook(account_id, token.access_token, req)
        return await self._publish_instagram(account_id, token.access_token, req, state)

    async def _publish_facebook(self, page_id: str, tok: str, req: PublishRequest) -> PublishResult:
        video = next((m for m in req.media if m.kind == "video"), None)
        image = next((m for m in req.media if m.kind == "image"), None)
        if video:
            data = await self._graph(
                "POST",
                f"{page_id}/videos",
                access_token=tok,
                file_url=video.url,
                description=req.caption,
            )
            return PublishResult(
                str(data["id"]), f"https://www.facebook.com/{page_id}/videos/{data['id']}"
            )
        if image:
            data = await self._graph(
                "POST", f"{page_id}/photos", access_token=tok, url=image.url, caption=req.caption
            )
            post_id = str(data.get("post_id") or data["id"])
        else:
            data = await self._graph(
                "POST", f"{page_id}/feed", access_token=tok, message=req.caption
            )
            post_id = str(data["id"])
        return PublishResult(post_id, f"https://www.facebook.com/{post_id}")

    async def _container(self, ig: str, tok: str, m: Any, **extra: str) -> str:
        field = {"video_url": m.url} if m.kind == "video" else {"image_url": m.url}
        data = await self._graph("POST", f"{ig}/media", access_token=tok, **field, **extra)
        return str(data["id"])

    async def _publish_instagram(
        self, ig: str, tok: str, req: PublishRequest, state: dict[str, Any]
    ) -> PublishResult:
        # The container id is kept in `state`, so a retry publishes the same upload.
        if not state.get("container_id"):
            if req.content_type is ContentType.CAROUSEL:
                children = [
                    await self._container(
                        ig,
                        tok,
                        m,
                        is_carousel_item="true",
                        **({"media_type": "VIDEO"} if m.kind == "video" else {}),
                    )
                    for m in req.media
                ]
                data = await self._graph(
                    "POST",
                    f"{ig}/media",
                    access_token=tok,
                    media_type="CAROUSEL",
                    children=",".join(children),
                    caption=req.caption,
                )
                state["container_id"] = str(data["id"])
            elif req.content_type is ContentType.STORY:
                state["container_id"] = await self._container(
                    ig, tok, req.media[0], media_type="STORIES"
                )
            elif req.media[0].kind == "video":
                state["container_id"] = await self._container(
                    ig, tok, req.media[0], media_type="REELS", caption=req.caption
                )
            else:
                state["container_id"] = await self._container(
                    ig, tok, req.media[0], caption=req.caption
                )
            state["container_created_at"] = utcnow().isoformat()
        status = await self._graph(
            "GET", state["container_id"], access_token=tok, fields="status_code"
        )
        code = status.get("status_code")
        if code in ("IN_PROGRESS", None) and any(m.kind == "video" for m in req.media):
            raise SocialError(
                "Instagram is still processing the video.", code="processing", processing=True
            )
        if code in ("ERROR", "EXPIRED"):
            state.pop("container_id", None)
            raise SocialError(
                "Instagram couldn't process the media. Check the file and try again.",
                code="media_rejected",
            )
        data = await self._graph(
            "POST", f"{ig}/media_publish", access_token=tok, creation_id=state["container_id"]
        )
        media_id = str(data["id"])
        link = await self._graph("GET", media_id, access_token=tok, fields="permalink")
        return PublishResult(media_id, link.get("permalink"))

    async def fetch_metrics(
        self,
        platform: Platform,
        account_id: str,
        token: TokenSet,
        post_id: str,
        ctype: ContentType,
    ) -> dict[str, float]:
        tok = token.access_token
        if platform is Platform.INSTAGRAM:
            names = ["reach", "saved", "shares", "likes", "comments", "total_interactions"]
            if ctype in (ContentType.REEL, ContentType.VIDEO):
                names.append("views")
            raw = _insight_values(
                await self._graph(
                    "GET", f"{post_id}/insights", access_token=tok, metric=",".join(names)
                )
            )
            rename = {"saved": "saves", "total_interactions": "interactions"}
            return {rename.get(k, k): v for k, v in raw.items()}
        fields = await self._graph(
            "GET",
            post_id,
            access_token=tok,
            fields="shares,comments.summary(true).limit(0),reactions.summary(true).limit(0)",
        )
        out: dict[str, float] = {}
        if "shares" in fields:
            out["shares"] = float(fields["shares"].get("count", 0))
        elif "reactions" in fields:
            # Facebook omits `shares` when nobody shared; with reactions present it's a real 0.
            out["shares"] = 0.0
        if "comments" in fields:
            out["comments"] = float(fields["comments"]["summary"]["total_count"])
        if "reactions" in fields:
            out["likes"] = float(fields["reactions"]["summary"]["total_count"])
        try:
            reach = _insight_values(
                await self._graph(
                    "GET", f"{post_id}/insights", access_token=tok, metric="post_impressions_unique"
                )
            )
            if "post_impressions_unique" in reach:
                out["reach"] = reach["post_impressions_unique"]
        except SocialError as exc:
            if exc.needs_reauth:
                raise  # otherwise: insights unavailable for this post type; keep what we have
        return out
