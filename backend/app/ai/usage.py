"""AI allowance accounting: reserve before calling a provider, commit or refund after.

Reservations count against the monthly quota immediately, and a row lock on the workspace
serialises concurrent reservations, so two parallel requests can't both take the last credit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import Completion
from app.billing.entitlements import calendar_month, usage_period, workspace_plan
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.models import AIResponseCache, AIUsage, ContentSchedule, Workspace
from app.models.enums import AIOperation, ScheduleStatus, UsageStatus, WorkspaceRole

# Which plan allowance each operation draws from.
BUCKETS: dict[str, tuple[AIOperation, ...]] = {
    "ai_content": (AIOperation.TEXT, AIOperation.REASONING),
    "images": (AIOperation.IMAGE,),
    "video_credits": (AIOperation.VIDEO,),
}


def bucket_of(op: AIOperation) -> str:
    return next(b for b, ops in BUCKETS.items() if op in ops)


@dataclass
class Allowance:
    used: int
    limit: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


async def _used(
    db: AsyncSession, ws: Workspace, bucket: str, start: datetime, end: datetime
) -> int:
    q = select(func.coalesce(func.sum(AIUsage.credits), 0)).where(
        AIUsage.workspace_id == ws.id,
        AIUsage.operation.in_(BUCKETS[bucket]),
        AIUsage.status.in_([UsageStatus.RESERVED, UsageStatus.COMMITTED]),
        AIUsage.created_at >= start,
        AIUsage.created_at < end,
    )
    return int((await db.execute(q)).scalar_one())


async def summary(db: AsyncSession, ws: Workspace) -> dict[str, Any]:
    plan = await workspace_plan(db, ws)
    start, end = await usage_period(db, ws)
    limits = {
        "ai_content": plan.ai_content,
        "images": plan.images,
        "video_credits": plan.video_credits,
    }
    out: dict[str, Any] = {"plan": plan.name.lower(), "period_start": start, "period_end": end}
    for bucket, limit in limits.items():
        used = await _used(db, ws, bucket, start, end)
        out[bucket] = {"used": used, "limit": limit, "remaining": max(0, limit - used)}
    # Scheduled posts are counted per calendar month of the scheduled date (this month here).
    month_start, month_end = calendar_month()
    scheduled = (
        await db.execute(
            select(func.count(func.distinct(ContentSchedule.content_id))).where(
                ContentSchedule.workspace_id == ws.id,
                ContentSchedule.status.in_([ScheduleStatus.PENDING, ScheduleStatus.QUEUED]),
                ContentSchedule.scheduled_at >= month_start,
                ContentSchedule.scheduled_at < month_end,
            )
        )
    ).scalar_one()
    out["scheduled_posts"] = {
        "used": scheduled,
        "limit": plan.scheduled_posts,
        "remaining": max(0, plan.scheduled_posts - scheduled),
    }
    return out


async def reserve(
    db: AsyncSession,
    ws: Workspace,
    *,
    user_id: uuid.UUID | None,
    operation: AIOperation,
    provider: str,
    model: str,
    credits: int = 1,
    fingerprint: str | None = None,
    content_id: uuid.UUID | None = None,
) -> AIUsage:
    await db.execute(select(Workspace.id).where(Workspace.id == ws.id).with_for_update())
    plan = await workspace_plan(db, ws)
    bucket = bucket_of(operation)
    limit = {
        "ai_content": plan.ai_content,
        "images": plan.images,
        "video_credits": plan.video_credits,
    }[bucket]
    start, end = await usage_period(db, ws)
    used = await _used(db, ws, bucket, start, end)
    if used + credits > limit:
        noun = {
            "ai_content": "AI content generations",
            "images": "image generations",
            "video_credits": "video credits",
        }[bucket]
        raise AppError(
            402,
            "quota_exceeded",
            f"You've used all {limit} {noun} for this month. They reset on "
            f"{end.strftime('%B')} {end.day}, or upgrade for more.",
            {"bucket": bucket, "used": used, "limit": limit, "resets_at": end.isoformat()},
        )
    usage = AIUsage(
        workspace_id=ws.id,
        user_id=user_id,
        operation=operation,
        status=UsageStatus.RESERVED,
        provider=provider,
        model=model,
        credits=credits,
        request_fingerprint=fingerprint,
        content_id=content_id,
    )
    db.add(usage)
    await db.flush()
    after = used + credits
    for threshold in (100, 80):
        if after * 100 >= limit * threshold > used * 100:
            from app.models.enums import NotificationType
            from app.notifications.service import notify

            noun = {
                "ai_content": "AI drafts",
                "images": "images",
                "video_credits": "video credits",
            }[bucket]
            await notify(
                db,
                workspace_id=ws.id,
                kind=NotificationType.QUOTA_WARNING,
                title=f"You've used {threshold}% of this period's {noun}",
                body=f"{after} of {limit} used. They reset on {end.strftime('%B')} {end.day}.",
                action_url="/settings/billing",
                dedupe=f"quota:{bucket}:{start.date()}:{threshold}",
                roles=(WorkspaceRole.OWNER, WorkspaceRole.ADMIN),
            )
            break
    return usage


def commit(usage: AIUsage, completion: Completion | None, *, cache_hit: bool = False) -> None:
    usage.status = UsageStatus.COMMITTED
    usage.finalized_at = utcnow()
    usage.cache_hit = cache_hit
    if cache_hit:
        usage.credits = 0  # reused result: not charged
    if completion:
        usage.model = completion.model
        usage.input_units = completion.input_tokens
        usage.output_units = completion.output_tokens
        usage.estimated_cost_usd = Decimal(str(round(completion.cost_usd, 6)))


def refund(usage: AIUsage) -> None:
    usage.status = UsageStatus.REFUNDED
    usage.finalized_at = utcnow()


async def cache_get(db: AsyncSession, ws_id: uuid.UUID, fingerprint: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(AIResponseCache.response).where(
                AIResponseCache.workspace_id == ws_id,
                AIResponseCache.fingerprint == fingerprint,
                AIResponseCache.expires_at > utcnow(),
            )
        )
    ).scalar_one_or_none()
    return row


async def cache_put(
    db: AsyncSession,
    ws_id: uuid.UUID,
    fingerprint: str,
    provider: str,
    model: str,
    response: dict[str, Any],
) -> None:
    expires = utcnow() + timedelta(hours=settings.AI_CACHE_TTL_HOURS)
    stmt = insert(AIResponseCache).values(
        workspace_id=ws_id,
        fingerprint=fingerprint,
        provider=provider,
        model=model,
        response=response,
        expires_at=expires,
    )
    await db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_ai_cache_ws_fp",
            set_={"response": response, "expires_at": expires, "model": model},
        )
    )
