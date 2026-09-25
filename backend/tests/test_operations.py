from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select, update

from app.content.service import run_generation
from app.core.database import SessionLocal
from app.models import AIUsage, ContentSchedule, Notification, User
from app.models.enums import AIOperation, UsageStatus
from app.notifications.reminders import send_reminders
from app.notifications.service import send_pending_emails
from app.social import publisher
from app.workers.queue import RecordingJobQueue
from tests.conftest import PASSWORD, register_verified


async def _ws(client: httpx.AsyncClient) -> str:
    return (await client.get("/workspaces")).json()[0]["id"]


async def test_reminders_overdue_and_email(
    client: httpx.AsyncClient, queue: RecordingJobQueue, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    await register_verified(client, queue, "remind@example.com", name="Nino")
    ws = await _ws(client)
    await client.put(
        f"/workspaces/{ws}/business/preferences", json={"reminder_offsets_hours": [24, 1]}
    )
    post = (
        await client.post(
            f"/workspaces/{ws}/content",
            json={"title": "Weekend hours", "platforms": ["instagram"], "caption": "x"},
        )
    ).json()
    await client.put(
        f"/workspaces/{ws}/content/{post['id']}/schedule",
        json={"scheduled_at": (datetime.now(UTC) + timedelta(hours=5)).isoformat()},
    )

    async with SessionLocal() as db:
        assert await send_reminders(db) == 1  # inside 24 h: first reminder
        assert await send_reminders(db) == 0  # never twice for the same offset
        await db.execute(
            update(ContentSchedule).values(scheduled_at=datetime.now(UTC) + timedelta(minutes=40))
        )
        await db.commit()
        assert await send_reminders(db) == 1  # inside 1 h: the urgent one

    page = (await client.get("/notifications")).json()
    assert page["unread"] == 2 and page["items"][0]["priority"] == "high"
    assert (
        page["items"][0]["title"].startswith("Approve \u201cWeekend hours\u201d")
        and page["items"][0]["action_url"] == f"/content/{post['id']}"
    )

    sent: list = []

    class Capture:
        async def send(self, message):  # type: ignore[no-untyped-def]
            sent.append(message)

    monkeypatch.setattr("app.notifications.email.providers.get_email_provider", lambda: Capture())
    async with SessionLocal() as db:
        assert await send_pending_emails(db) == 2  # reminders are emailed by default
        assert await send_pending_emails(db) == 0
    assert (
        sent[0].to == "remind@example.com"
        and "needs your approval" not in sent[0].subject
        and "Hi Nino" in sent[0].text
    )

    # Overdue: the time passes without approval
    async with SessionLocal() as db:
        await db.execute(
            update(ContentSchedule).values(scheduled_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await db.commit()
        await publisher.enqueue_due(db, queue)
    kinds = [n["type"] for n in (await client.get("/notifications")).json()["items"]]
    assert kinds[0] == "approval_overdue"

    assert (await client.post("/notifications/read-all")).status_code == 204
    assert (await client.get("/notifications")).json()["unread"] == 0


async def test_preferences_turn_email_off_and_in_app_off(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "prefs@example.com")
    ws = await _ws(client)
    prefs = (await client.get(f"/workspaces/{ws}/notification-preferences")).json()
    reminder = next(p for p in prefs if p["type"] == "pre_publish_reminder")
    assert reminder == {
        "type": "pre_publish_reminder",
        "label": "Posts waiting for approval",
        "in_app": True,
        "email": True,
    }
    r = await client.put(
        f"/workspaces/{ws}/notification-preferences",
        json=[{"type": "pre_publish_reminder", "in_app": False, "email": False}],
    )
    assert next(p for p in r.json() if p["type"] == "pre_publish_reminder")["in_app"] is False
    post = (
        await client.post(
            f"/workspaces/{ws}/content",
            json={"title": "Muted", "platforms": ["instagram"], "caption": "x"},
        )
    ).json()
    await client.put(
        f"/workspaces/{ws}/content/{post['id']}/schedule",
        json={"scheduled_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat()},
    )
    async with SessionLocal() as db:
        assert await send_reminders(db) == 0  # both channels off: nothing created
    assert (await client.get("/notifications")).json()["items"] == []


async def test_quota_warning_and_agent_activity(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    from app.ai.mock import MockProvider

    await register_verified(client, queue, "agent@example.com")
    ws = await _ws(client)
    async with SessionLocal() as db:
        for _ in range(7):
            db.add(
                AIUsage(
                    workspace_id=uuid.UUID(ws),
                    operation=AIOperation.TEXT,
                    status=UsageStatus.COMMITTED,
                    provider="mock",
                    model="m",
                )
            )
        await db.commit()
    await client.post(
        f"/workspaces/{ws}/content/generate",
        json={"idea": "Our cold brew", "platforms": ["instagram"]},
    )
    job = queue.last("generate_content")
    async with SessionLocal() as db:
        await run_generation(
            db, MockProvider(), uuid.UUID(job["content_id"]), uuid.UUID(job["usage_id"])
        )
    notes = (await client.get("/notifications")).json()["items"]
    assert any(n["type"] == "quota_warning" and "80%" in n["title"] for n in notes)  # 8 of 10 used

    runs = (await client.get(f"/workspaces/{ws}/agent/runs")).json()
    draft = runs[0]
    assert (
        draft["agent"] == "content"
        and draft["status"] == "succeeded"
        and draft["trigger"] == "user"
    )
    assert [s["position"] for s in draft["steps"]] == [0, 1, 2]
    assert draft["steps"][2]["title"].startswith("Wrote the post for Instagram")
    assert draft["limits"]["max_steps"] == 20


async def test_admin_area(client: httpx.AsyncClient, queue: RecordingJobQueue, make_client) -> None:  # type: ignore[no-untyped-def]
    await register_verified(client, queue, "boss@example.com")
    member = await make_client()
    await register_verified(member, queue, "customer@example.com")
    assert (await client.get("/admin/overview")).status_code == 403  # not a superuser yet
    async with SessionLocal() as db:
        await db.execute(
            update(User).where(User.email == "boss@example.com").values(is_superuser=True)
        )
        await db.commit()
    overview = (await client.get("/admin/overview")).json()
    assert overview["users"] == 2 and overview["plans"]["free"] == 2 and overview["mrr_usd"] == 0
    users = (await client.get("/admin/users", params={"q": "customer"})).json()
    assert [u["email"] for u in users] == ["customer@example.com"] and users[0][
        "status"
    ] == "active"

    r = await client.post(f"/admin/users/{users[0]['id']}/suspend", json={"reason": "Spam reports"})
    assert r.status_code == 204
    assert (await member.get("/auth/me")).status_code == 401  # existing session ended at once
    login = await member.post(
        "/auth/login", json={"email": "customer@example.com", "password": PASSWORD}
    )
    assert login.status_code == 403 and login.json()["error"]["code"] == "account_suspended"
    me = (await client.get("/auth/me")).json()
    assert (
        await client.post(f"/admin/users/{me['id']}/suspend", json={"reason": "oops"})
    ).status_code == 409
    log = (await client.get("/admin/audit-log", params={"action": "admin."})).json()
    assert log[0]["action"] == "admin.user_suspended" and log[0]["actor"] == "boss@example.com"
    assert (await client.post(f"/admin/users/{users[0]['id']}/unsuspend")).status_code == 204
    assert (
        await member.post(
            "/auth/login", json={"email": "customer@example.com", "password": PASSWORD}
        )
    ).status_code == 200
    async with SessionLocal() as db:
        assert (await db.execute(select(Notification))).scalars().all() == []
