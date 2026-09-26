"""Re-enqueue work whose queued job was lost.

The job queue lives in Redis. If Redis loses its data (a restart on a plan without
persistence, a flush, a failover), anything that was queued but not yet run is gone, and
the database would show it as in progress forever: a draft stuck on "generating", an upload
stuck on "processing". This sweep finds such rows and enqueues their job again.

It's safe to run while jobs are healthy: it only looks at work older than the job's own
time limit (plus margin), the jobs use fixed ids so arq refuses a copy of one that is still
queued or running (app/workers/queue.py), and every job re-checks the database state first
(a finished draft's usage is no longer "reserved", a processed file is no longer
"processing"), so a late duplicate does nothing.

Scheduled posts don't need this: enqueue_due_publications already rebuilds publishing work
from the database every minute.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import utcnow
from app.models import AIUsage, Content, MediaAsset
from app.models.enums import AIOperation, ContentStatus, MediaSource, MediaStatus, UsageStatus
from app.workers.queue import get_queue

log = logging.getLogger("contentfactory.recovery")

# Longer than each job's timeout in app/workers/settings.py, so a slow job is never doubled.
TEXT_AFTER = timedelta(minutes=10)  # generate_content: 3 min timeout
IMAGE_AFTER = timedelta(minutes=15)  # generate_image: 5 min
VIDEO_AFTER = timedelta(minutes=30)  # render_video: 20 min
PROCESS_AFTER = timedelta(minutes=50)  # process_media: 15 min x 3 tries
GIVE_UP_AFTER = timedelta(days=2)  # older than this is left alone (and visible to support)


async def recover_lost_jobs(ctx: dict[str, Any] | None = None) -> int:
    now = utcnow()
    queue = get_queue()
    found = 0
    async with SessionLocal() as db:
        reserved = (
            await db.scalars(
                select(AIUsage).where(
                    AIUsage.status == UsageStatus.RESERVED,
                    AIUsage.created_at < now - TEXT_AFTER,
                    AIUsage.created_at > now - GIVE_UP_AFTER,
                )
            )
        ).all()
        for usage in reserved:
            age = now - usage.created_at
            if usage.operation in (AIOperation.TEXT, AIOperation.REASONING) and usage.content_id:
                content = await db.get(Content, usage.content_id)
                if content is not None and content.status is ContentStatus.GENERATING:
                    await queue.enqueue(
                        "generate_content", content_id=str(content.id), usage_id=str(usage.id)
                    )
                    found += 1
            elif usage.operation in (AIOperation.IMAGE, AIOperation.VIDEO):
                limit = IMAGE_AFTER if usage.operation is AIOperation.IMAGE else VIDEO_AFTER
                if age < limit:
                    continue
                asset = await db.scalar(
                    select(MediaAsset).where(
                        MediaAsset.ai_metadata["usage_id"].astext == str(usage.id),
                        MediaAsset.status == MediaStatus.PROCESSING,
                        MediaAsset.deleted_at.is_(None),
                    )
                )
                if asset is not None:
                    job = (
                        "generate_image" if usage.operation is AIOperation.IMAGE else "render_video"
                    )
                    await queue.enqueue(job, asset_id=str(asset.id), usage_id=str(usage.id))
                    found += 1

        uploads = (
            await db.scalars(
                select(MediaAsset).where(
                    MediaAsset.status == MediaStatus.PROCESSING,
                    MediaAsset.source == MediaSource.UPLOAD,
                    MediaAsset.deleted_at.is_(None),
                    MediaAsset.updated_at < now - PROCESS_AFTER,
                    MediaAsset.updated_at > now - GIVE_UP_AFTER,
                )
            )
        ).all()
        for asset in uploads:
            await queue.enqueue("process_media", asset_id=str(asset.id))
            found += 1
    if found:
        log.warning("re-enqueued %d job(s) whose queue entry was lost", found)
    return found
