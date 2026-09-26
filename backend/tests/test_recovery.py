"""Work whose queued job was lost (Redis restarted without persistence) is enqueued again."""

from __future__ import annotations

import uuid
from datetime import timedelta

import httpx
from sqlalchemy import update

from app.core.database import SessionLocal
from app.core.security import utcnow
from app.models import AIUsage, MediaAsset
from app.workers.jobs.recovery import recover_lost_jobs
from app.workers.queue import RecordingJobQueue, job_id
from tests.conftest import register_verified
from tests.media_helpers import png_bytes, upload


async def _ws(client: httpx.AsyncClient) -> str:
    return (await client.get("/workspaces")).json()[0]["id"]


async def test_stuck_draft_and_upload_are_requeued_once_old_enough(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "recover@example.com")
    ws = await _ws(client)
    await client.put(f"/workspaces/{ws}/business/profile", json={"name": "Lab", "industry": "Café"})
    r = await client.post(
        f"/workspaces/{ws}/content/generate",
        json={"idea": "Cold brew", "platforms": ["instagram"], "goal": "more_visits"},
    )
    assert r.status_code == 202, r.text
    job = queue.last("generate_content")

    # Fresh work is left alone: its job may still be queued or running.
    queue.jobs.clear()
    assert await recover_lost_jobs() == 0 and queue.jobs == []

    # Pretend Redis lost the queue 20 minutes ago: the draft is still "generating".
    async with SessionLocal() as db:
        await db.execute(
            update(AIUsage)
            .where(AIUsage.id == uuid.UUID(job["usage_id"]))
            .values(created_at=utcnow() - timedelta(minutes=20))
        )
        await db.commit()
    assert await recover_lost_jobs() == 1
    assert queue.jobs == [("generate_content", job)]

    # An upload stuck in "processing" for an hour is processed again.
    asset = await upload(client, ws, png_bytes(), filename="p.png")
    async with SessionLocal() as db:
        await db.execute(
            update(MediaAsset)
            .where(MediaAsset.id == uuid.UUID(asset["id"]))
            .values(status="processing", updated_at=utcnow() - timedelta(hours=1))
        )
        await db.commit()
    queue.jobs.clear()
    assert await recover_lost_jobs() == 2
    assert ("process_media", {"asset_id": asset["id"]}) in queue.jobs


def test_deduped_jobs_get_a_stable_id() -> None:
    assert job_id("generate_content", {"content_id": "c", "usage_id": "u"}) == "generate_content:u"
    assert job_id("process_media", {"asset_id": "a"}) == "process_media:a"
    assert job_id("send_email", {"to": "x"}) is None  # everything else keeps random ids


async def test_arq_queue_keeps_a_callers_own_job_id() -> None:
    """The publisher passes its own _job_id; the queue must not add a second one."""
    from typing import Any

    from app.workers.queue import ArqJobQueue

    calls: list[tuple[str, dict[str, Any]]] = []

    class FakePool:
        async def enqueue_job(self, job: str, **kwargs: Any) -> None:
            calls.append((job, kwargs))

    q = ArqJobQueue()
    q._pool = FakePool()  # type: ignore[assignment]
    await q.enqueue("publish_publication", publication_id="p1", _job_id="publish:p1:0")
    await q.enqueue("generate_content", content_id="c", usage_id="u")
    await q.enqueue("send_email", to="x@example.com")
    assert calls == [
        ("publish_publication", {"publication_id": "p1", "_job_id": "publish:p1:0"}),
        ("generate_content", {"content_id": "c", "usage_id": "u", "_job_id": "generate_content:u"}),
        ("send_email", {"to": "x@example.com", "_job_id": None}),
    ]
