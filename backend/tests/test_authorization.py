from __future__ import annotations

import uuid
from datetime import date, timedelta

import httpx
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import MarketingInsight, Workspace
from app.models.enums import Confidence, InsightCategory, InsightStatus
from app.workers.queue import RecordingJobQueue
from tests.conftest import register_verified


async def _workspace_id(client: httpx.AsyncClient) -> str:
    return (await client.get("/workspaces")).json()[0]["id"]


async def test_unauthenticated_requests_are_rejected(client: httpx.AsyncClient) -> None:
    assert (await client.get("/workspaces")).status_code == 401
    assert (await client.get(f"/workspaces/{uuid.uuid4()}/dashboard")).status_code == 401


async def test_user_cannot_access_another_workspace(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    make_client,  # type: ignore[no-untyped-def]
) -> None:
    await register_verified(client, queue, "alice@example.com", "Alice")
    alice_ws = await _workspace_id(client)

    bob = await make_client()
    await register_verified(bob, queue, "bob@example.com", "Bob")
    bob_ws = await _workspace_id(bob)
    assert alice_ws != bob_ws

    for path in (f"/workspaces/{alice_ws}", f"/workspaces/{alice_ws}/dashboard"):
        r = await bob.get(path)
        assert r.status_code == 404, path  # 404, not 403: don't confirm the workspace exists
    r = await bob.patch(f"/workspaces/{alice_ws}", json={"name": "pwned"})
    assert r.status_code == 404
    assert (await client.get(f"/workspaces/{alice_ws}")).json()["name"] == "Alice's business"
    assert [w["id"] for w in (await bob.get("/workspaces")).json()] == [bob_ws]


async def test_new_workspace_dashboard_shows_real_empty_state(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "new@example.com")
    ws = await _workspace_id(client)
    d = (await client.get(f"/workspaces/{ws}/dashboard")).json()
    assert d["week"]["created"] == 0 and d["week"]["awaiting_approval"] == 0
    assert d["performance"]["posts_measured"] == 0 and d["performance"]["reach"] is None
    kinds = [a["kind"] for a in d["attention"]]
    assert kinds == ["finish_onboarding", "connect_account"]
    assert d["upcoming"] == [] and d["agent"] == [] and d["learned"] == []


async def test_insights_below_minimum_sample_are_hidden(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "ins@example.com")
    ws_id = uuid.UUID(await _workspace_id(client))
    async with SessionLocal() as db:
        assert (await db.execute(select(Workspace).where(Workspace.id == ws_id))).scalar_one()
        for size, text in ((3, "tiny sample"), (12, "real finding")):
            db.add(
                MarketingInsight(
                    workspace_id=ws_id,
                    category=InsightCategory.FORMAT,
                    status=InsightStatus.ACTIVE,
                    title=text,
                    statement=text,
                    metric="saves",
                    sample_size=size,
                    period_start=date.today() - timedelta(days=30),
                    period_end=date.today(),
                    confidence=Confidence.MEDIUM,
                )
            )
        await db.commit()
    learned = (await client.get(f"/workspaces/{ws_id}/dashboard")).json()["learned"]
    assert [i["statement"] for i in learned] == ["real finding"]


async def test_viewer_cannot_rename_workspace(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    make_client,  # type: ignore[no-untyped-def]
) -> None:
    from app.models import User, WorkspaceMember
    from app.models.enums import WorkspaceRole

    await register_verified(client, queue, "own@example.com")
    ws_id = uuid.UUID(await _workspace_id(client))
    viewer = await make_client()
    await register_verified(viewer, queue, "view@example.com")
    async with SessionLocal() as db:
        v = (await db.execute(select(User).where(User.email == "view@example.com"))).scalar_one()
        db.add(WorkspaceMember(workspace_id=ws_id, user_id=v.id, role=WorkspaceRole.VIEWER))
        await db.commit()
    assert (await viewer.get(f"/workspaces/{ws_id}/dashboard")).status_code == 200
    r = await viewer.patch(f"/workspaces/{ws_id}", json={"name": "renamed"})
    assert r.status_code == 403
