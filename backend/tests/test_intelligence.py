from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update

from app.ai.base import Completion, CompletionRequest
from app.ai.mock import MockProvider
from app.ai.providers import set_provider
from app.analytics.collector import collect_one, interval_for
from app.content.service import run_generation
from app.core.config import settings
from app.core.crypto import encrypt
from app.core.database import SessionLocal
from app.models import (
    Content,
    MetricSnapshot,
    PlatformMetric,
    Publication,
    SocialAccount,
    SocialAccountToken,
    Subscription,
)
from app.models.enums import (
    ContentStatus,
    ContentType,
    Plan,
    Platform,
    PublicationStatus,
    SocialAccountStatus,
)
from app.social import registry
from app.social.adapters.meta import MetaAdapter
from app.workers.queue import RecordingJobQueue
from tests.conftest import register_verified

V = settings.META_GRAPH_VERSION


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


async def _post(
    ws: str,
    *,
    pillar: str,
    platform: Platform = Platform.INSTAGRAM,
    hour: int = 18,
    days_ago: int = 3,
    **metrics: int | None,
) -> uuid.UUID:
    """A published post with metrics, as the collector would have stored them."""
    async with SessionLocal() as db:
        c = Content(
            workspace_id=uuid.UUID(ws),
            status=ContentStatus.PUBLISHED,
            content_type=ContentType.POST,
            origin="manual",
            title=f"{pillar} post",
            pillar=pillar,
            hashtags=[],
            attributes={},
        )
        db.add(c)
        await db.flush()
        at = (datetime.now(UTC) - timedelta(days=days_ago)).replace(hour=hour, minute=0)
        p = Publication(
            workspace_id=c.workspace_id,
            content_id=c.id,
            platform=platform,
            idempotency_key=uuid.uuid4().hex,
            status=PublicationStatus.PUBLISHED,
            scheduled_at=at,
            published_at=at,
            platform_post_id=uuid.uuid4().hex[:10],
        )
        db.add(p)
        await db.flush()
        if metrics:
            db.add(
                PlatformMetric(
                    workspace_id=c.workspace_id,
                    publication_id=p.id,
                    platform=platform,
                    available_metrics=[k for k, v in metrics.items() if v is not None],
                    **metrics,
                )
            )
        await db.commit()
        return c.id


def fake_graph(request: httpx.Request) -> httpx.Response:
    path = request.url.path.removeprefix(f"/{V}/")
    if path == "ig_media/insights":
        metrics = request.url.params["metric"].split(",")
        assert "views" not in metrics  # a photo post: views aren't requested
        values = {
            "reach": 820,
            "saved": 41,
            "shares": 9,
            "likes": 120,
            "comments": 14,
            "total_interactions": 184,
        }
        return httpx.Response(
            200, json={"data": [{"name": m, "total_value": {"value": values[m]}} for m in metrics]}
        )
    if path == "fb_post":
        return httpx.Response(
            200,
            json={
                "id": "fb_post",
                "comments": {"summary": {"total_count": 3}},
                "reactions": {"summary": {"total_count": 25}},
            },
        )
    if path == "fb_post/insights":
        return httpx.Response(
            400, json={"error": {"code": 100, "message": "metric not available for this post"}}
        )
    return httpx.Response(404, json={"error": {"code": 803}})


async def test_metrics_collection_keeps_unreported_metrics_null(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "metrics@example.com")
    ws = uuid.UUID(await _ws(client))
    registry.set_adapters(
        {
            "meta": MetaAdapter(
                httpx.AsyncClient(
                    transport=httpx.MockTransport(fake_graph), base_url="https://graph.facebook.com"
                )
            )
        }
    )
    try:
        async with SessionLocal() as db:
            pubs = {}
            for platform, post_id in (
                (Platform.INSTAGRAM, "ig_media"),
                (Platform.FACEBOOK, "fb_post"),
            ):
                acc = SocialAccount(
                    workspace_id=ws,
                    platform=platform,
                    external_account_id=f"acc_{platform.value}",
                    status=SocialAccountStatus.CONNECTED,
                )
                db.add(acc)
                c = Content(
                    workspace_id=ws,
                    status=ContentStatus.PUBLISHED,
                    content_type=ContentType.POST,
                    origin="manual",
                    title="x",
                    hashtags=[],
                    attributes={},
                )
                db.add(c)
                await db.flush()
                db.add(
                    SocialAccountToken(
                        social_account_id=acc.id, access_token_encrypted=encrypt("tok")
                    )
                )
                pubs[platform] = Publication(
                    workspace_id=ws,
                    content_id=c.id,
                    social_account_id=acc.id,
                    platform=platform,
                    idempotency_key=post_id,
                    status=PublicationStatus.PUBLISHED,
                    scheduled_at=datetime.now(UTC),
                    published_at=datetime.now(UTC),
                    platform_post_id=post_id,
                )
                db.add(pubs[platform])
            await db.commit()
            for p in pubs.values():
                assert await collect_one(db, p)
            ig = (
                await db.execute(
                    select(PlatformMetric).where(
                        PlatformMetric.publication_id == pubs[Platform.INSTAGRAM].id
                    )
                )
            ).scalar_one()
            assert (ig.reach, ig.saves, ig.views) == (820, 41, None)
            assert "views" not in ig.available_metrics and float(ig.engagement_rate) == round(
                (41 + 9 + 120 + 14) / 820, 5
            )
            fb = (
                await db.execute(
                    select(PlatformMetric).where(
                        PlatformMetric.publication_id == pubs[Platform.FACEBOOK].id
                    )
                )
            ).scalar_one()
            assert (fb.likes, fb.comments, fb.shares, fb.reach, fb.saves) == (25, 3, 0, None, None)
            assert len((await db.execute(select(MetricSnapshot))).scalars().all()) == 2
    finally:
        registry.set_adapters(None)
    assert interval_for(timedelta(hours=5)) == timedelta(hours=6)
    assert interval_for(timedelta(days=10)) == timedelta(days=7)
    assert interval_for(timedelta(days=40)) is None


async def test_analytics_overview(client: httpx.AsyncClient, queue: RecordingJobQueue) -> None:
    await register_verified(client, queue, "analytics@example.com")
    ws = await _ws(client)
    await _post(ws, pillar="educational", reach=1000, likes=50, saves=30)
    await _post(
        ws, pillar="promotional", platform=Platform.FACEBOOK, reach=400, likes=10, comments=2
    )
    await _post(ws, pillar="community")  # published, not measured yet
    a = (await client.get(f"/workspaces/{ws}/analytics?days=30")).json()
    assert (a["posts_published"], a["posts_measured"]) == (3, 2)
    assert a["totals"]["reach"] == 1400 and a["totals"]["views"] is None  # never reported: not zero
    assert a["totals"]["engagements"] == 50 + 30 + 10 + 2
    fb = next(p for p in a["platforms"] if p["platform"] == "facebook")
    assert "saves" in fb["unavailable"] and "views" in fb["unavailable"]
    assert len(a["daily"]) == 30 and sum(d["posts"] for d in a["daily"]) == 3
    assert a["top_posts"][0]["title"] == "educational post"


async def test_insights_need_evidence(client: httpx.AsyncClient, queue: RecordingJobQueue) -> None:
    await register_verified(client, queue, "insights@example.com")
    ws = await _ws(client)
    for i in range(4):  # too few posts: nothing may be claimed
        await _post(ws, pillar="educational", saves=40 + i, hour=10)
        await _post(ws, pillar="promotional", saves=10 + i, hour=10)
    await client.post(f"/workspaces/{ws}/insights/refresh")
    assert (await client.get(f"/workspaces/{ws}/insights")).json() == []

    for i in range(3):
        await _post(ws, pillar="educational", saves=35 + i, hour=10)
        await _post(ws, pillar="promotional", saves=12 + i, hour=10)
    r = (await client.post(f"/workspaces/{ws}/insights/refresh")).json()
    assert r["created"] == 1
    [ins] = (await client.get(f"/workspaces/{ws}/insights")).json()
    assert (
        ins["statement"].startswith("Educational posts averaged")
        and "saves versus" in ins["statement"]
    )
    assert ins["sample_size"] == 14 and ins["evidence"]["n_a"] == 7 and ins["confidence"] == "low"
    assert (await client.post(f"/workspaces/{ws}/insights/refresh")).json() == {
        "created": 0,
        "updated": 1,
        "superseded": 0,
    }

    mem = (await client.post(f"/workspaces/{ws}/insights/{ins['id']}/remember")).json()
    assert (
        mem["source"] == "analytics"
        and mem["category"] == "successful_topic"
        and mem["evidence"]["sample_size"] == 14
    )
    again = (await client.post(f"/workspaces/{ws}/insights/{ins['id']}/remember")).json()
    assert again["id"] == mem["id"]  # remembered once

    await client.post(f"/workspaces/{ws}/insights/{ins['id']}/dismiss")
    await client.post(f"/workspaces/{ws}/insights/refresh")
    assert (
        await client.get(f"/workspaces/{ws}/insights")
    ).json() == []  # a recent dismissal is respected


async def test_memory_search_and_use_in_drafts(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "memory@example.com")
    ws = await _ws(client)
    for text, cat, pin in (
        ("Regulars love the oat milk cappuccino, mention it often", "audience", False),
        ("Reels posted on Friday evenings reach the most people", "posting_time", False),
        ("Never mention competitors by name", "brand", True),
    ):
        assert (
            await client.post(
                f"/workspaces/{ws}/memory", json={"content": text, "category": cat, "pinned": pin}
            )
        ).status_code == 201
    hits = (
        await client.get(f"/workspaces/{ws}/memory", params={"q": "oat milk cappuccino"})
    ).json()
    assert hits[0]["content"].startswith("Regulars love the oat milk")
    listed = (await client.get(f"/workspaces/{ws}/memory")).json()
    assert listed[0]["pinned"] is True and len(listed) == 3

    seen: dict = {}

    class Capture(MockProvider):
        async def complete(self, req: CompletionRequest) -> Completion:
            seen["prompt"] = req.prompt
            return await super().complete(req)

    set_provider(Capture())
    try:
        r = await client.post(
            f"/workspaces/{ws}/content/generate",
            json={"idea": "Our oat milk cappuccino", "platforms": ["instagram"]},
        )
        job = queue.last("generate_content")
        async with SessionLocal() as db:
            await run_generation(
                db, Capture(), uuid.UUID(job["content_id"]), uuid.UUID(job["usage_id"])
            )
    finally:
        set_provider(None)
    block = seen["prompt"].split("<what_we_learned>")[1].split("</what_we_learned>")[0]
    assert "Never mention competitors" in block and "oat milk cappuccino" in block
    assert r.status_code == 202

    mid = listed[1]["id"]
    edited = (
        await client.patch(
            f"/workspaces/{ws}/memory/{mid}",
            json={"content": "Reels on Friday evenings reach the most people", "pinned": True},
        )
    ).json()
    assert edited["pinned"] is True
    assert (await client.delete(f"/workspaces/{ws}/memory/{mid}")).status_code == 204
    assert len((await client.get(f"/workspaces/{ws}/memory")).json()) == 2


async def test_experiments(client: httpx.AsyncClient, queue: RecordingJobQueue) -> None:
    user = await register_verified(client, queue, "exp@example.com")
    ws = await _ws(client)
    body = {
        "name": "Question hooks",
        "hypothesis": "Questions get more comments",
        "variable": "hook",
        "primary_metric": "engagements",
        "variant_a": "Hook is a question",
        "variant_b": "Hook is a statement",
        "min_sample_per_variant": 3,
    }
    r = await client.post(f"/workspaces/{ws}/experiments", json=body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "plan_required"  # Free
    await _plan(user["id"], Plan.STARTER)
    exp = (await client.post(f"/workspaces/{ws}/experiments", json=body)).json()
    assert (
        await client.post(f"/workspaces/{ws}/experiments", json=body)
    ).status_code == 409  # Starter: 1 at a time

    a_posts = [await _post(ws, pillar="educational", likes=60 + i, comments=10) for i in range(3)]
    b_posts = [await _post(ws, pillar="educational", likes=20 + i, comments=2) for i in range(2)]
    await client.put(
        f"/workspaces/{ws}/experiments/{exp['id']}/variants/A",
        json={"content_ids": [str(x) for x in a_posts]},
    )
    r = await client.put(
        f"/workspaces/{ws}/experiments/{exp['id']}/variants/B",
        json={"content_ids": [str(a_posts[0])]},
    )
    assert r.status_code == 422  # a post can't be in both variants
    await client.put(
        f"/workspaces/{ws}/experiments/{exp['id']}/variants/B",
        json={"content_ids": [str(x) for x in b_posts]},
    )

    still = (await client.post(f"/workspaces/{ws}/experiments/{exp['id']}/evaluate")).json()
    assert still["status"] == "running" and still["result"]["enough_data"] is False

    b_posts.append(await _post(ws, pillar="educational", likes=25, comments=3))
    await client.put(
        f"/workspaces/{ws}/experiments/{exp['id']}/variants/B",
        json={"content_ids": [str(x) for x in b_posts]},
    )
    done = (await client.post(f"/workspaces/{ws}/experiments/{exp['id']}/evaluate")).json()
    assert done["status"] == "completed" and done["conclusion"].startswith(
        "A (Hook is a question) beat B"
    )
    winner = next(v for v in done["variants"] if v["id"] == done["winner_variant_id"])
    assert winner["label"] == "A" and winner["sample_size"] == 3
    memories = (await client.get(f"/workspaces/{ws}/memory")).json()
    assert memories[0]["source"] == "experiment" and "Question hooks" in memories[0]["content"]
    assert (
        await client.post(f"/workspaces/{ws}/experiments", json=body)
    ).status_code == 201  # slot freed


@pytest.fixture(autouse=True)
def _reset_adapters():  # type: ignore[no-untyped-def]
    yield
    registry.set_adapters(None)
