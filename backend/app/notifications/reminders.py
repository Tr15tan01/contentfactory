"""Pre-publish approval reminders at the offsets each workspace chose (24 h, 6 h, 1 h)."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models import Content, ContentSchedule, Workspace
from app.models.enums import ContentStatus, NotificationType, ScheduleStatus
from app.notifications.service import notify


async def send_reminders(db: AsyncSession) -> int:
    now = utcnow()
    rows = (
        await db.execute(
            select(
                ContentSchedule.content_id, ContentSchedule.scheduled_at, Content.title, Workspace
            )
            .join(Content, Content.id == ContentSchedule.content_id)
            .join(Workspace, Workspace.id == ContentSchedule.workspace_id)
            .where(
                ContentSchedule.status == ScheduleStatus.PENDING,
                ContentSchedule.scheduled_at > now,
                ContentSchedule.scheduled_at <= now + timedelta(hours=24),
                Content.status.in_(
                    [ContentStatus.AWAITING_APPROVAL, ContentStatus.READY, ContentStatus.DRAFT]
                ),
                Content.deleted_at.is_(None),
            )
        )
    ).all()
    sent = 0
    seen: set = set()
    for content_id, when, title, ws in rows:
        if content_id in seen:
            continue  # one reminder per post, not per platform
        seen.add(content_id)
        offsets = sorted((ws.settings or {}).get("reminder_offsets_hours", [24]))
        due = [h for h in offsets if when - timedelta(hours=h) <= now]
        if not due:
            continue
        hours = min(due)  # the most urgent offset reached
        local = when.astimezone(ZoneInfo(ws.timezone or "UTC"))
        sent += await notify(
            db,
            workspace_id=ws.id,
            kind=NotificationType.PRE_PUBLISH_REMINDER,
            title=f"Approve \u201c{title}\u201d before {local.strftime('%a %H:%M')}",
            body="Approve, edit or reschedule it. If it isn't approved, it won't be published.",
            action_url=f"/content/{content_id}",
            dedupe=f"reminder:{content_id}:{when.isoformat()}:{hours}",
            priority="high" if hours <= 1 else "normal",
            entity=("content", content_id),
        )
    await db.commit()
    return sent
