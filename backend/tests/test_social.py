from __future__ import annotations

import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from PIL import Image
from sqlalchemy import select, update

from app.core.config import settings
from app.core.crypto import decrypt
from app.core.database import SessionLocal
from app.models import (
    ContentSchedule,
    Publication,
    SocialAccount,
    SocialAccountToken,
    Subscription,
    User,
    WorkspaceMember,
)
from app.models.enums import Plan, Platform, PublicationStatus, SocialAccountStatus, WorkspaceRole
from app.social import publisher, registry
from app.social.adapters.meta import MetaAdapter
from app.social.adapters.tiktok import TikTokAdapter
from app.social.adapters.youtube import YouTubeAdapter
from app.social.base import MediaItem, PublishRequest, TokenSet
from app.social.service import refresh_due_tokens
from app.workers.queue import RecordingJobQueue
from tests.conftest import register_verified
from tests.media_helpers import upload

V = settings.META_GRAPH_VERSION


class FakeMeta:
    """Just enough of the Graph API, recording every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []
        self.fail_publish_once = False
        self.token_invalid = False
        self.pages = [
            {
                "id": "page1",
                "name": "Tbilisi Coffee Lab",
                "access_token": "PAGE1-TOKEN",
                "instagram_business_account": {"id": "ig1", "username": "tbilisicoffeelab"},
            },
            {"id": "page2", "name": "Coffee Lab Events", "access_token": "PAGE2-TOKEN"},
        ]

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix(f"/{V}/")
        params = (
            dict(request.url.params)
            if request.method == "GET"
            else {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        )
        self.calls.append((request.method, path, params))
        if self.token_invalid and path != "oauth/access_token":
            return httpx.Response(400, json={"error": {"code": 190, "message": "Session expired"}})
        if path == "oauth/access_token":
            return httpx.Response(
                200, json={"access_token": "LONG" if "fb_exchange_token" in params else "SHORT"}
            )
        if path == "me/accounts":
            return httpx.Response(200, json={"data": self.pages})
        if path.endswith("/media") and request.method == "POST":
            return httpx.Response(200, json={"id": f"container{len(self.calls)}"})
        if path.startswith("container"):
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if path.endswith("/media_publish"):
            if self.fail_publish_once:
                self.fail_publish_once = False
                return httpx.Response(
                    500, json={"error": {"code": 2, "message": "Service temporarily unavailable"}}
                )
            return httpx.Response(200, json={"id": "igmedia1"})
        if path == "igmedia1":
            return httpx.Response(200, json={"permalink": "https://www.instagram.com/p/ABC123/"})
        if path.endswith("/photos"):
            return httpx.Response(200, json={"id": "photo1", "post_id": "page1_987"})
        return httpx.Response(404, json={"error": {"code": 803, "message": f"unknown {path}"}})

    def count(self, suffix: str) -> int:
        return sum(1 for m, p, _ in self.calls if p.endswith(suffix) and m == "POST")


@pytest.fixture
def meta(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(settings, "META_CLIENT_ID", "meta-app")
    monkeypatch.setattr(settings, "META_CLIENT_SECRET", "meta-secret")
    fake = FakeMeta()
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(fake.handler), base_url="https://graph.facebook.com"
    )
    registry.set_adapters(
        {"meta": MetaAdapter(client), "tiktok": TikTokAdapter(), "youtube": YouTubeAdapter()}
    )
    yield fake
    registry.set_adapters(None)


async def _ws(client: httpx.AsyncClient) -> str:
    return (await client.get("/workspaces")).json()[0]["id"]


async def _plan(user_id: str, plan: Plan) -> None:
    async with SessionLocal() as db:
        await db.execute(
            update(Subscription)
            .where(Subscription.user_id == uuid.UUID(user_id))
            .values(manual_plan_override=plan)
        )
        await db.commit()


async def _connect_meta(client: httpx.AsyncClient, ws: str) -> httpx.Response:
    r = await client.post(f"/workspaces/{ws}/social/meta/connect")
    assert r.status_code == 200, r.text
    state = parse_qs(urlparse(r.json()["authorize_url"]).query)["state"][0]
    return await client.get(f"/social/callback/meta?code=abc&state={state}", follow_redirects=False)


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1080, 1350), (180, 120, 60)).save(buf, "JPEG", quality=85)
    return buf.getvalue()


async def test_connect_flow_limits_and_encryption(
    client: httpx.AsyncClient, queue: RecordingJobQueue, meta: FakeMeta
) -> None:
    user = await register_verified(client, queue, "social@example.com")
    ws = await _ws(client)
    r = await client.post(f"/workspaces/{ws}/social/meta/connect")
    url = urlparse(r.json()["authorize_url"])
    q = parse_qs(url.query)
    assert (
        url.netloc == "www.facebook.com"
        and q["client_id"] == ["meta-app"]
        and "instagram_content_publish" in q["scope"][0]
    )
    assert q["redirect_uri"][0].endswith("/api/v1/social/callback/meta")

    bad = await client.get("/social/callback/meta?code=abc&state=forged", follow_redirects=False)
    assert bad.status_code == 303 and "error=state_invalid" in bad.headers["location"]

    # Free plan allows 1 account: the login offers 3 (two Pages, one Instagram)
    r = await _connect_meta(client, ws)
    assert (
        r.status_code == 303
        and "connected=1" in r.headers["location"]
        and "skipped=2" in r.headers["location"]
    )
    await _plan(user["id"], Plan.BUSINESS)
    r = await _connect_meta(client, ws)
    assert "connected=2" in r.headers["location"] and "reconnected=1" in r.headers["location"]

    social = (await client.get(f"/workspaces/{ws}/social")).json()
    assert social["limit"] == {"used": 3, "limit": 8}
    assert {a["platform"] for a in social["accounts"]} == {"facebook", "instagram"}
    assert social["publishing_needs_public_media"] is True  # local storage in tests
    async with SessionLocal() as db:
        row = (await db.execute(select(SocialAccountToken))).scalars().first()
        assert row is not None and b"PAGE" not in row.access_token_encrypted
        assert decrypt(row.access_token_encrypted).startswith("PAGE")

    # Disconnect removes the tokens themselves
    ig = next(a for a in social["accounts"] if a["platform"] == "instagram")
    assert (await client.delete(f"/workspaces/{ws}/social/accounts/{ig['id']}")).status_code == 204
    async with SessionLocal() as db:
        assert (
            await db.execute(
                select(SocialAccountToken).where(
                    SocialAccountToken.social_account_id == uuid.UUID(ig["id"])
                )
            )
        ).first() is None


async def test_unconfigured_and_permissions(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    make_client,  # type: ignore[no-untyped-def]
) -> None:
    await register_verified(client, queue, "unconf@example.com")
    ws = await _ws(client)
    r = await client.post(f"/workspaces/{ws}/social/tiktok/connect")
    assert r.status_code == 503 and r.json()["error"]["code"] == "provider_unavailable"
    providers = {
        p["provider"]: p for p in (await client.get(f"/workspaces/{ws}/social")).json()["providers"]
    }
    assert providers["tiktok"]["configured"] is False
    editor = await make_client()
    await register_verified(editor, queue, "ed-social@example.com")
    async with SessionLocal() as db:
        u = (
            await db.execute(select(User).where(User.email == "ed-social@example.com"))
        ).scalar_one()
        db.add(WorkspaceMember(workspace_id=uuid.UUID(ws), user_id=u.id, role=WorkspaceRole.EDITOR))
        await db.commit()
    assert (await editor.post(f"/workspaces/{ws}/social/meta/connect")).status_code == 403


async def _scheduled_post(
    client: httpx.AsyncClient, ws: str, platforms: list[str], media: list[str]
) -> dict:
    post = (
        await client.post(
            f"/workspaces/{ws}/content",
            json={
                "title": "Morning bake",
                "platforms": platforms,
                "caption": "Fresh from the oven.",
                "hashtags": ["Tbilisi"],
                "media_ids": media,
            },
        )
    ).json()
    await client.post(f"/workspaces/{ws}/content/{post['id']}/approve")
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert (
        await client.put(
            f"/workspaces/{ws}/content/{post['id']}/schedule", json={"scheduled_at": when}
        )
    ).json()["status"] == "scheduled"
    async with SessionLocal() as db:  # time passes
        await db.execute(
            update(ContentSchedule)
            .where(ContentSchedule.content_id == uuid.UUID(post["id"]))
            .values(scheduled_at=datetime.now(UTC) - timedelta(seconds=5))
        )
        await db.commit()
    return post


async def _due(queue: RecordingJobQueue) -> dict:
    async with SessionLocal() as db:
        return await publisher.enqueue_due(db, queue)


async def _publish(queue: RecordingJobQueue) -> PublicationStatus | None:
    job = queue.last("publish_publication")
    async with SessionLocal() as db:
        return await publisher.publish(db, queue, uuid.UUID(job["publication_id"]))


async def test_instagram_publish_is_idempotent_and_retries(
    client: httpx.AsyncClient, queue: RecordingJobQueue, meta: FakeMeta
) -> None:
    user = await register_verified(client, queue, "pub@example.com")
    await _plan(user["id"], Plan.BUSINESS)
    ws = await _ws(client)
    await _connect_meta(client, ws)
    photo = await upload(client, ws, _jpeg(), filename="bread.jpg", content_type="image/jpeg")
    post = await _scheduled_post(client, ws, ["instagram"], [photo["id"]])

    assert (await _due(queue))["queued"] == 1
    assert (await _due(queue))["queued"] == 0  # a second scheduler pass creates nothing
    async with SessionLocal() as db:
        assert len((await db.execute(select(Publication))).scalars().all()) == 1

    meta.fail_publish_once = True
    assert await _publish(queue) is PublicationStatus.QUEUED  # 500 from Meta: retry later
    retry_job = queue.last("publish_publication")
    assert retry_job["_defer_by"] >= 55
    assert (await client.get(f"/workspaces/{ws}/content/{post['id']}")).json()[
        "status"
    ] == "publishing"

    assert await _publish(queue) is PublicationStatus.PUBLISHED
    assert meta.count("/media") == 1  # the retry reused the same container: no duplicate upload
    container = next(p for m, path, p in meta.calls if path == "ig1/media")
    assert container["image_url"].startswith("http") and "#Tbilisi" in container["caption"]
    detail = (await client.get(f"/workspaces/{ws}/content/{post['id']}")).json()
    assert detail["status"] == "published"
    assert detail["publications"][0]["platform_url"] == "https://www.instagram.com/p/ABC123/"
    assert (await _publish(queue)) is PublicationStatus.PUBLISHED and meta.count(
        "/media_publish"
    ) == 2  # 1 failed + 1 ok; replay did nothing


async def test_expired_access_missing_account_and_manual_retry(
    client: httpx.AsyncClient, queue: RecordingJobQueue, meta: FakeMeta
) -> None:
    user = await register_verified(client, queue, "reauth@example.com")
    await _plan(user["id"], Plan.BUSINESS)
    ws = await _ws(client)
    await _connect_meta(client, ws)
    accounts = (await client.get(f"/workspaces/{ws}/social")).json()["accounts"]
    ig = next(a for a in accounts if a["platform"] == "instagram")
    await client.delete(f"/workspaces/{ws}/social/accounts/{ig['id']}")
    photo = await upload(client, ws, _jpeg(), filename="cake.jpg", content_type="image/jpeg")
    post = await _scheduled_post(client, ws, ["facebook", "instagram"], [photo["id"]])
    await _due(queue)
    detail = (await client.get(f"/workspaces/{ws}/content/{post['id']}")).json()
    missing = next(p for p in detail["publications"] if p["platform"] == "instagram")
    assert missing["status"] == "failed" and missing["error_code"] == "not_connected"
    assert "Instagram" in missing["error_message"] and detail["missing_accounts"] == ["instagram"]

    meta.token_invalid = True
    assert await _publish(queue) is PublicationStatus.FAILED
    async with SessionLocal() as db:
        fb = (
            await db.execute(
                select(SocialAccount).where(SocialAccount.external_account_id == "page1")
            )
        ).scalar_one()
        assert fb.status is SocialAccountStatus.EXPIRED and "Reconnect" in (fb.last_error or "")
    detail = (await client.get(f"/workspaces/{ws}/content/{post['id']}")).json()
    assert detail["status"] == "failed"
    fb_pub = next(p for p in detail["publications"] if p["platform"] == "facebook")
    assert fb_pub["error_code"] == "needs_reauth"
    dash = (await client.get(f"/workspaces/{ws}/dashboard")).json()
    assert {"renew_connection", "publication_failed"} <= {a["kind"] for a in dash["attention"]}

    assert (
        await client.post(f"/workspaces/{ws}/publications/{fb_pub['id']}/retry")
    ).status_code == 409  # still expired
    meta.token_invalid = False
    meta.pages = meta.pages[:1]  # reconnecting also brings Instagram back
    await _connect_meta(client, ws)
    r = await client.post(f"/workspaces/{ws}/publications/{fb_pub['id']}/retry")
    assert r.status_code == 200 and r.json()["status"] == "queued"
    assert await _publish(queue) is PublicationStatus.PUBLISHED
    fb_pub = next(
        p
        for p in (await client.get(f"/workspaces/{ws}/content/{post['id']}")).json()["publications"]
        if p["platform"] == "facebook"
    )
    assert fb_pub["platform_url"] == "https://www.facebook.com/page1_987"


async def test_overdue_approval_and_unknown_outcome(
    client: httpx.AsyncClient, queue: RecordingJobQueue, meta: FakeMeta
) -> None:
    await register_verified(client, queue, "overdue@example.com")
    ws = await _ws(client)
    post = (
        await client.post(
            f"/workspaces/{ws}/content",
            json={"title": "Never approved", "platforms": ["instagram"], "caption": "x"},
        )
    ).json()
    await client.put(
        f"/workspaces/{ws}/content/{post['id']}/schedule",
        json={"scheduled_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
    )
    async with SessionLocal() as db:
        await db.execute(
            update(ContentSchedule).values(scheduled_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await db.commit()
    stats = await _due(queue)
    assert stats["overdue"] == 1 and stats["queued"] == 0
    async with SessionLocal() as db:
        assert (
            not (await db.execute(select(Publication))).scalars().all()
        )  # never published without approval

        pub = Publication(
            workspace_id=uuid.UUID(ws),
            content_id=uuid.UUID(post["id"]),
            platform=Platform.INSTAGRAM,
            idempotency_key="stuck-1",
            status=PublicationStatus.PUBLISHING,
            scheduled_at=datetime.now(UTC),
            last_attempt_at=datetime.now(UTC) - timedelta(minutes=20),
        )
        db.add(pub)
        await db.commit()
    assert (await _due(queue))["unknown"] == 1
    async with SessionLocal() as db:
        stuck = (
            await db.execute(select(Publication).where(Publication.idempotency_key == "stuck-1"))
        ).scalar_one()
        assert stuck.status is PublicationStatus.FAILED and stuck.error_code == "unknown_outcome"


async def test_tiktok_and_youtube_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TIKTOK_CLIENT_KEY", "tk")
    monkeypatch.setattr(settings, "TIKTOK_CLIENT_SECRET", "ts")
    polls = {"n": 0}
    tiktok_upload: list[tuple[dict, bytes]] = []

    def tiktok(request: httpx.Request) -> httpx.Response:
        body = (
            json.loads(request.content or b"{}")
            if request.headers.get("content-type", "").startswith("application/json")
            else {}
        )
        if request.url.path.endswith("creator_info/query/"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "privacy_level_options": ["SELF_ONLY"],
                        "creator_username": "labtbilisi",
                    },
                    "error": {"code": "ok"},
                },
            )
        if request.url.path.endswith("video/init/"):
            assert body["post_info"]["privacy_level"] == "SELF_ONLY"
            assert body["source_info"] == {
                "source": "FILE_UPLOAD",
                "video_size": 6,
                "chunk_size": 6,
                "total_chunk_count": 1,
            }
            return httpx.Response(
                200,
                json={
                    "data": {
                        "publish_id": "pub_1",
                        "upload_url": "https://upload.tiktok.example/up/1",
                    },
                    "error": {"code": "ok"},
                },
            )
        if request.url.host == "upload.tiktok.example":
            tiktok_upload.append((dict(request.headers), request.content))
            return httpx.Response(201)
        if request.url.path.endswith("status/fetch/"):
            polls["n"] += 1
            status = "PROCESSING_DOWNLOAD" if polls["n"] == 1 else "PUBLISH_COMPLETE"
            return httpx.Response(
                200,
                json={
                    "data": {"status": status, "publicaly_available_post_id": [7300]},
                    "error": {"code": "ok"},
                },
            )
        return httpx.Response(404)

    tk = TikTokAdapter(
        httpx.AsyncClient(
            transport=httpx.MockTransport(tiktok), base_url="https://open.tiktokapis.com"
        )
    )

    async def six_bytes():  # type: ignore[no-untyped-def]
        yield b"abc"
        yield b"def"

    video = MediaItem(
        kind="video",
        url="https://cdn.example/v.mp4",
        mime_type="video/mp4",
        size_bytes=6,
        open=six_bytes,
    )
    req = PublishRequest(
        platform=Platform.TIKTOK,
        content_type=__import__("app.models.enums", fromlist=["ContentType"]).ContentType.REEL,
        title="t",
        caption="Cold brew",
        media=[video],
    )
    state: dict = {}
    with pytest.raises(Exception) as processing:
        await tk.publish("open1", TokenSet("tok"), req, state)
    assert getattr(processing.value, "processing", False) and state["publish_id"] == "pub_1"
    [(headers, body)] = tiktok_upload  # pushed once, in one piece: no domain to verify
    assert body == b"abcdef" and headers["content-range"] == "bytes 0-5/6"
    assert headers["content-type"] == "video/mp4" and headers["content-length"] == "6"
    result = await tk.publish("open1", TokenSet("tok"), req, state)
    assert len(tiktok_upload) == 1  # polling doesn't upload again
    assert (
        result.url == "https://www.tiktok.com/@labtbilisi/video/7300"
        and result.details["privacy_level"] == "SELF_ONLY"
    )

    uploaded = {}

    def google(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/youtube/v3/videos":
            uploaded["meta"] = json.loads(request.content)
            return httpx.Response(200, headers={"location": "https://upload.example/session/1"})
        if request.url.host == "upload.example":
            uploaded["bytes"] = request.content
            return httpx.Response(200, json={"id": "yt123", "status": {"privacyStatus": "private"}})
        return httpx.Response(404)

    async def chunks():  # type: ignore[no-untyped-def]
        yield b"abc"
        yield b"def"

    yt = YouTubeAdapter(httpx.AsyncClient(transport=httpx.MockTransport(google)))
    video.open = chunks
    from app.models.enums import ContentType

    res = await yt.publish(
        "chan",
        TokenSet("tok"),
        PublishRequest(
            Platform.YOUTUBE, ContentType.SHORT, "Cold brew in 15s", "Eighteen hours.", [video]
        ),
        {},
    )
    assert (
        uploaded["bytes"] == b"abcdef" and "#Shorts" in uploaded["meta"]["snippet"]["description"]
    )
    assert (
        res.url == "https://www.youtube.com/shorts/yt123"
        and res.details["privacy_status"] == "private"
    )


async def test_token_refresh_job(
    client: httpx.AsyncClient, queue: RecordingJobQueue, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.crypto import encrypt

    monkeypatch.setattr(settings, "TIKTOK_CLIENT_KEY", "tk")
    monkeypatch.setattr(settings, "TIKTOK_CLIENT_SECRET", "ts")

    def handler(request: httpx.Request) -> httpx.Response:
        form = parse_qs(request.content.decode())
        if form.get("refresh_token") == ["good"]:
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "good2",
                    "expires_in": 86400,
                    "refresh_expires_in": 3e7,
                },
            )
        return httpx.Response(
            200, json={"error": {"code": "access_token_invalid", "message": "invalid"}}
        )

    registry.set_adapters(
        {
            "tiktok": TikTokAdapter(
                httpx.AsyncClient(
                    transport=httpx.MockTransport(handler), base_url="https://open.tiktokapis.com"
                )
            )
        }
    )
    try:
        await register_verified(client, queue, "refresh@example.com")
        ws = uuid.UUID(await _ws(client))
        async with SessionLocal() as db:
            for ext, refresh in (("ok", "good"), ("bad", "revoked")):
                acc = SocialAccount(
                    workspace_id=ws,
                    platform=Platform.TIKTOK,
                    external_account_id=ext,
                    status=SocialAccountStatus.CONNECTED,
                )
                db.add(acc)
                await db.flush()
                db.add(
                    SocialAccountToken(
                        social_account_id=acc.id,
                        access_token_encrypted=encrypt("old"),
                        refresh_token_encrypted=encrypt(refresh),
                        expires_at=datetime.now(UTC) + timedelta(hours=2),
                    )
                )
            await db.commit()
            stats = await refresh_due_tokens(db)
        assert stats == {"refreshed": 1, "expired": 1, "failed": 0}
        async with SessionLocal() as db:
            rows = {
                a.external_account_id: a
                for a in (await db.execute(select(SocialAccount))).scalars()
            }
            assert (
                rows["ok"].status is SocialAccountStatus.CONNECTED
                and rows["bad"].status is SocialAccountStatus.EXPIRED
            )
            tok = (
                await db.execute(
                    select(SocialAccountToken).where(
                        SocialAccountToken.social_account_id == rows["ok"].id
                    )
                )
            ).scalar_one()
            assert decrypt(tok.access_token_encrypted) == "new-access"
    finally:
        registry.set_adapters(None)


def test_meta_login_uses_config_id_for_business_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings
    from app.social.adapters.meta import SCOPES, MetaAdapter

    monkeypatch.setattr(settings, "META_CLIENT_ID", "app-id")
    redirect = "https://app.example.com/api/v1/social/callback/meta"
    classic = parse_qs(urlparse(MetaAdapter().authorize_url("st", "v", redirect)).query)
    assert classic["scope"] == [",".join(SCOPES)] and "config_id" not in classic

    monkeypatch.setattr(settings, "META_LOGIN_CONFIG_ID", "1234567890")
    business = parse_qs(urlparse(MetaAdapter().authorize_url("st", "v", redirect)).query)
    assert business["config_id"] == ["1234567890"] and "scope" not in business
    assert business["redirect_uri"] == [redirect] and business["response_type"] == ["code"]


def test_tiktok_chunk_plan_follows_the_media_transfer_rules() -> None:
    from app.social.adapters.tiktok import CHUNK_BYTES, chunk_plan

    mb = 1024 * 1024
    assert chunk_plan(3 * mb) == (3 * mb, 1)  # under 5 MB: one piece
    assert chunk_plan(7 * mb) == (7 * mb, 1)  # 5-10 MB: one piece within 5-64 MB
    assert chunk_plan(25 * mb) == (CHUNK_BYTES, 2)  # 10 + 15 MB (final chunk absorbs the rest)
    for size in (10 * mb, 25 * mb + 17, 500 * mb):
        chunk, count = chunk_plan(size)
        final = size - chunk * (count - 1)
        assert 5 * mb <= chunk <= 64 * mb and 1 <= count <= 1000
        assert chunk <= final < 128 * mb and count == size // chunk


async def test_tiktok_multi_chunk_upload_and_restart_after_interruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.models.enums import ContentType
    from app.social.adapters.tiktok import CHUNK_BYTES
    from app.social.base import SocialError

    size = CHUNK_BYTES * 2 + 12345
    puts: list[str] = []
    inits = {"n": 0}
    fail_second_put = {"on": True}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("creator_info/query/"):
            return httpx.Response(
                200,
                json={"data": {"privacy_level_options": ["SELF_ONLY"]}, "error": {"code": "ok"}},
            )
        if request.url.path.endswith("video/init/"):
            inits["n"] += 1
            src = json.loads(request.content)["source_info"]
            assert (src["chunk_size"], src["total_chunk_count"]) == (CHUNK_BYTES, 2)
            return httpx.Response(
                200,
                json={
                    "data": {"publish_id": f"p{inits['n']}", "upload_url": "https://up.example/u"},
                    "error": {"code": "ok"},
                },
            )
        if request.url.host == "up.example":
            puts.append(request.headers["content-range"])
            assert len(request.content) == int(request.headers["content-length"])
            if len(puts) == 2 and fail_second_put["on"]:
                fail_second_put["on"] = False
                raise httpx.WriteError("connection reset")
            last = request.headers["content-range"].endswith(f"-{size - 1}/{size}")
            return httpx.Response(201 if last else 206)
        if request.url.path.endswith("status/fetch/"):
            return httpx.Response(
                200, json={"data": {"status": "PROCESSING_UPLOAD"}, "error": {"code": "ok"}}
            )
        return httpx.Response(404)

    async def stream():  # type: ignore[no-untyped-def]
        sent = 0
        while sent < size:  # storage streams 1 MB pieces, not TikTok-sized chunks
            n = min(1024 * 1024, size - sent)
            sent += n
            yield b"x" * n

    tk = TikTokAdapter(
        httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://open.tiktokapis.com"
        )
    )
    video = MediaItem(kind="video", url="", mime_type="video/mp4", size_bytes=size, open=stream)
    req = PublishRequest(
        platform=Platform.TIKTOK,
        content_type=ContentType.REEL,
        title="t",
        caption="c",
        media=[video],
    )
    state: dict = {}
    with pytest.raises(SocialError) as interrupted:
        await tk.publish("open1", TokenSet("tok"), req, state)
    assert interrupted.value.retryable and "publish_id" not in state

    puts.clear()
    with pytest.raises(SocialError) as processing:
        await tk.publish("open1", TokenSet("tok"), req, state)
    assert processing.value.processing and state["publish_id"] == "p2" and inits["n"] == 2
    assert puts == [
        f"bytes 0-{CHUNK_BYTES - 1}/{size}",
        f"bytes {CHUNK_BYTES}-{size - 1}/{size}",
    ]

    bad = MediaItem(kind="video", url="", mime_type="video/x-msvideo", size_bytes=1)
    assert tk.validate(
        PublishRequest(
            platform=Platform.TIKTOK,
            content_type=ContentType.REEL,
            title="",
            caption="",
            media=[bad],
        )
    ) == ["TikTok accepts MP4, MOV or WebM videos."]


async def test_tiktok_regroups_the_storage_stream_into_exact_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.social.adapters import tiktok
    from app.social.base import SocialError

    monkeypatch.setattr(tiktok, "CHUNK_BYTES", 4)

    async def stream(parts):  # type: ignore[no-untyped-def]
        for p in parts:
            yield p

    got = [c async for c in tiktok._chunks(stream([b"ab", b"cdefg", b"hij"]), 10)]
    assert got == [(0, b"abcd"), (4, b"efghij")]  # re-cut to exact chunks, last one larger
    with pytest.raises(SocialError, match="shorter"):
        _ = [c async for c in tiktok._chunks(stream([b"abc"]), 10)]
