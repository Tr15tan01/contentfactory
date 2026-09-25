from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.billing import paddle
from app.billing.service import set_manual_plan
from app.core.config import settings
from app.core.database import SessionLocal
from app.main import create_app
from app.models import AuditLog, BillingEvent, Subscription
from app.models.enums import Plan
from app.workers.queue import RecordingJobQueue
from tests.conftest import register_verified

SECRET = "pdl_ntfset_test_secret"
PRICES = {"starter": "pri_starter", "business": "pri_business", "agency": "pri_agency"}


@pytest.fixture
def paddle_env(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    for k, v in {
        "PADDLE_API_KEY": "pdl_sdbx_apikey_test",
        "PADDLE_CLIENT_TOKEN": "test_clienttoken",
        "PADDLE_WEBHOOK_SECRET": SECRET,
        "PADDLE_STARTER_PRICE_ID": PRICES["starter"],
        "PADDLE_BUSINESS_PRICE_ID": PRICES["business"],
        "PADDLE_AGENCY_PRICE_ID": PRICES["agency"],
    }.items():
        monkeypatch.setattr(settings, k, v)
    yield
    paddle.set_paddle(None)


@pytest.fixture
async def raw_client():  # type: ignore[no-untyped-def]
    """No cookies, no CSRF header: exactly what Paddle's servers send."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://testserver/api/v1"
    ) as c:
        yield c


def signed(body: bytes, ts: int | None = None, secret: str = SECRET) -> dict[str, str]:
    ts = ts or int(time.time())
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return {"paddle-signature": f"ts={ts};h1={h1}", "content-type": "application/json"}


def event(  # noqa: PLR0913
    user_id: str | None,
    *,
    plan: str = "starter",
    status: str = "active",
    eid: str | None = None,
    at: datetime | None = None,
    sub_id: str = "sub_01test",
    scheduled: dict | None = None,
    sig: str | None = None,
    kind: str = "subscription.updated",
) -> bytes:
    at = at or datetime.now(UTC)
    start = datetime.now(UTC) - timedelta(days=3)
    custom = (
        {"user_id": user_id, "sig": sig or paddle.sign_custom_data(user_id)} if user_id else None
    )
    price = {
        "id": PRICES.get(plan, plan),
        "product_id": "pro_1",
        "billing_cycle": {"interval": "month", "frequency": 1},
        "unit_price": {"amount": "1900", "currency_code": "USD"},
    }
    period = {"starts_at": start.isoformat(), "ends_at": (start + timedelta(days=30)).isoformat()}
    data = {
        "id": sub_id,
        "status": status,
        "customer_id": "ctm_01test",
        "custom_data": custom,
        "items": [{"price": price, "quantity": 1}],
        "current_billing_period": period,
        "scheduled_change": scheduled,
    }
    return json.dumps(
        {
            "event_id": eid or f"evt_{uuid.uuid4().hex}",
            "event_type": kind,
            "occurred_at": at.isoformat().replace("+00:00", "Z"),
            "data": data,
        }
    ).encode()


async def _sub(user_id: str) -> Subscription:
    async with SessionLocal() as db:
        return (
            await db.execute(select(Subscription).where(Subscription.user_id == uuid.UUID(user_id)))
        ).scalar_one()


async def test_billing_unconfigured_is_honest(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "nobill@example.com")
    b = (await client.get("/billing")).json()
    assert b["configured"] is False and b["plan"] == "free" and b["client_token"] is None
    r = await client.post("/billing/checkout", json={"plan": "starter"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "billing_unavailable"


async def test_checkout_and_webhook_lifecycle(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    raw_client: httpx.AsyncClient,
    paddle_env: None,
) -> None:
    user = await register_verified(client, queue, "buyer@example.com")
    uid = user["id"]
    co = (await client.post("/billing/checkout", json={"plan": "business"})).json()
    assert co["price_id"] == PRICES["business"] and co["customer_email"] == "buyer@example.com"
    assert paddle.custom_data_user(co["custom_data"]) == uid

    # Signature failures change nothing
    body = event(uid, plan="business", kind="subscription.created")
    assert (
        await raw_client.post(
            "/billing/webhooks/paddle", content=body, headers={"content-type": "application/json"}
        )
    ).status_code == 401
    assert (
        await raw_client.post(
            "/billing/webhooks/paddle", content=body, headers=signed(body, secret="wrong")
        )
    ).status_code == 401
    assert (
        await raw_client.post(
            "/billing/webhooks/paddle",
            content=body,
            headers=signed(body, ts=int(time.time()) - 3600),
        )
    ).status_code == 401
    assert (await client.get("/billing")).json()["plan"] == "free"

    r = await raw_client.post("/billing/webhooks/paddle", content=body, headers=signed(body))
    assert r.status_code == 200 and r.json()["status"] == "applied"
    b = (await client.get("/billing")).json()
    assert b["plan"] == "business" and b["has_paddle_subscription"] and b["price_cents"] == 1900
    ws = (await client.get("/workspaces")).json()[0]["id"]
    usage = (await client.get(f"/workspaces/{ws}/usage")).json()
    assert usage["plan"] == "business" and usage["ai_content"]["limit"] == 250
    assert usage["period_start"].startswith(
        b["current_period_start"][:10]
    )  # Paddle period, not calendar month

    # Same delivery twice: stored once
    again = await raw_client.post("/billing/webhooks/paddle", content=body, headers=signed(body))
    assert again.json()["status"] == "duplicate"
    async with SessionLocal() as db:
        assert len((await db.execute(select(BillingEvent))).scalars().all()) == 1

    # Checkout again is refused: change the plan instead
    assert (await client.post("/billing/checkout", json={"plan": "agency"})).status_code == 409


async def test_out_of_order_unknown_price_and_forged_custom_data(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    raw_client: httpx.AsyncClient,
    paddle_env: None,
) -> None:
    user = await register_verified(client, queue, "order@example.com")
    uid = user["id"]
    now = datetime.now(UTC)
    newer = event(uid, plan="agency", at=now)
    older = event(uid, plan="starter", at=now - timedelta(minutes=5))
    assert (
        await raw_client.post("/billing/webhooks/paddle", content=newer, headers=signed(newer))
    ).json()["status"] == "applied"
    assert (
        await raw_client.post("/billing/webhooks/paddle", content=older, headers=signed(older))
    ).json()["status"] == "stale"
    assert (await client.get("/billing")).json()["plan"] == "agency"

    weird = event(uid, plan="pri_unknown", at=now + timedelta(minutes=1))
    assert (
        await raw_client.post("/billing/webhooks/paddle", content=weird, headers=signed(weird))
    ).json()["status"] == "unknown_price"
    assert (await client.get("/billing")).json()["plan"] == "agency"

    # Someone else's user id with a made-up signature on a new subscription: ignored
    victim = await register_verified(client, queue, "victim@example.com")
    forged = event(
        victim["id"], plan="agency", sub_id="sub_other", sig="0" * 40, at=now + timedelta(minutes=2)
    )
    assert (
        await raw_client.post("/billing/webhooks/paddle", content=forged, headers=signed(forged))
    ).json()["status"] == "unmatched"
    assert (await _sub(victim["id"])).plan is Plan.FREE


async def test_downgrade_and_status_rules(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    raw_client: httpx.AsyncClient,
    paddle_env: None,
) -> None:
    user = await register_verified(client, queue, "down@example.com")
    uid = user["id"]
    ws = (await client.get("/workspaces")).json()[0]["id"]
    t = datetime.now(UTC)
    up = event(uid, plan="business", at=t)
    await raw_client.post("/billing/webhooks/paddle", content=up, headers=signed(up))
    assert (
        await client.put(
            f"/workspaces/{ws}/business/preferences", json={"approval_required": False}
        )
    ).status_code == 200

    past_due = event(uid, plan="business", status="past_due", at=t + timedelta(seconds=1))
    await raw_client.post("/billing/webhooks/paddle", content=past_due, headers=signed(past_due))
    assert (await client.get("/billing")).json()[
        "plan"
    ] == "business"  # access kept while Paddle retries

    down = event(uid, plan="starter", at=t + timedelta(seconds=2))
    await raw_client.post("/billing/webhooks/paddle", content=down, headers=signed(down))
    prefs = (await client.get(f"/workspaces/{ws}/business")).json()["preferences"]
    assert prefs["approval_required"] is True  # auto-publish isn't on Starter

    cancel_sched = event(
        uid,
        plan="starter",
        at=t + timedelta(seconds=3),
        scheduled={"action": "cancel", "effective_at": "2030-01-01T00:00:00Z"},
    )
    await raw_client.post(
        "/billing/webhooks/paddle", content=cancel_sched, headers=signed(cancel_sched)
    )
    assert (await client.get("/billing")).json()["scheduled_change"]["action"] == "cancel"

    gone = event(uid, plan="starter", status="canceled", at=t + timedelta(seconds=4))
    await raw_client.post("/billing/webhooks/paddle", content=gone, headers=signed(gone))
    b = (await client.get("/billing")).json()
    assert (
        b["plan"] == "free" and b["status"] == "canceled" and b["has_paddle_subscription"] is False
    )
    async with SessionLocal() as db:
        actions = (
            (await db.execute(select(AuditLog.action).where(AuditLog.action.like("billing.%"))))
            .scalars()
            .all()
        )
        assert actions.count("billing.subscription_updated") == 5


async def test_plan_changes_call_paddle(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    raw_client: httpx.AsyncClient,
    paddle_env: None,
) -> None:
    calls: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        calls.append((request.method, request.url.path, body))
        assert request.headers["authorization"] == "Bearer pdl_sdbx_apikey_test"
        if request.url.path.endswith("/portal-sessions"):
            return httpx.Response(
                201,
                json={
                    "data": {
                        "urls": {
                            "general": {"overview": "https://customer-portal.paddle.com/cpl_1"}
                        }
                    }
                },
            )
        return httpx.Response(200, json={"data": {"id": "sub_01test"}})

    paddle.set_paddle(
        paddle.PaddleClient(
            httpx.AsyncClient(
                transport=httpx.MockTransport(handler), base_url="https://sandbox-api.paddle.com"
            )
        )
    )
    user = await register_verified(client, queue, "change@example.com")
    assert (
        await client.post("/billing/change-plan", json={"plan": "agency"})
    ).status_code == 409  # no subscription yet
    created = event(user["id"], plan="starter", kind="subscription.created")
    await raw_client.post("/billing/webhooks/paddle", content=created, headers=signed(created))

    r = await client.post("/billing/change-plan", json={"plan": "agency"})
    assert r.status_code == 202 and r.json() == {"status": "pending", "direction": "upgrade"}
    assert calls[-1] == (
        "PATCH",
        "/subscriptions/sub_01test",
        {
            "items": [{"price_id": PRICES["agency"], "quantity": 1}],
            "proration_billing_mode": "prorated_immediately",
        },
    )
    assert (await client.get("/billing")).json()[
        "plan"
    ] == "starter"  # unchanged until Paddle's webhook arrives
    assert (await client.post("/billing/change-plan", json={"plan": "free"})).status_code == 422

    assert (await client.post("/billing/cancel")).status_code == 202
    assert calls[-1] == (
        "POST",
        "/subscriptions/sub_01test/cancel",
        {"effective_from": "next_billing_period"},
    )
    assert (
        await client.post("/billing/resume")
    ).status_code == 409  # no scheduled change recorded yet
    portal = (await client.post("/billing/portal")).json()
    assert portal["url"].startswith("https://customer-portal.paddle.com/")


async def test_manual_plan_override_is_audited(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "vip@example.com")
    async with SessionLocal() as db:
        await set_manual_plan(db, "vip@example.com", Plan.AGENCY, "tests")
    b = (await client.get("/billing")).json()
    assert b["plan"] == "agency" and b["manual_override"] == "agency"
    async with SessionLocal() as db:
        await set_manual_plan(db, "vip@example.com", None, "tests")
        assert (
            (await db.execute(select(AuditLog).where(AuditLog.action == "billing.manual_plan_set")))
            .scalars()
            .all()
        )
    assert (await client.get("/billing")).json()["plan"] == "free"
