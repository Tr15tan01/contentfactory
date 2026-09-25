"""Which plan applies to a workspace, and over which period its allowances are counted."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.plans import PLANS, PlanLimits
from app.core.errors import AppError
from app.core.security import utcnow
from app.models import Subscription, Workspace
from app.models.enums import Plan, SubscriptionStatus

ACTIVE = (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING, SubscriptionStatus.PAST_DUE)


async def user_subscription(db: AsyncSession, user_id: uuid.UUID) -> Subscription | None:
    return (
        await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def effective_plan(sub: Subscription | None) -> Plan:
    """Manual overrides win; otherwise the paid plan while the subscription is usable.
    Past-due keeps access during Paddle's retry period; paused or canceled falls back to Free."""
    if sub is None:
        return Plan.FREE
    if sub.manual_plan_override is not None:
        return sub.manual_plan_override
    return sub.plan if sub.status in ACTIVE else Plan.FREE


async def workspace_plan(db: AsyncSession, ws: Workspace) -> PlanLimits:
    """A workspace uses its owner's subscription."""
    return PLANS[effective_plan(await user_subscription(db, ws.owner_id))]


def calendar_month(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = (now or utcnow()).astimezone(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, (start + timedelta(days=32)).replace(day=1)


async def usage_period(db: AsyncSession, ws: Workspace) -> tuple[datetime, datetime]:
    """Paid plans count allowances over the Paddle billing period; Free uses calendar months."""
    sub = await user_subscription(db, ws.owner_id)
    now = utcnow()
    if (
        sub
        and effective_plan(sub) is not Plan.FREE
        and sub.current_period_start
        and sub.current_period_end
        and sub.current_period_start <= now < sub.current_period_end
    ):
        return sub.current_period_start, sub.current_period_end
    return calendar_month(now)


def plan_required(feature: str, needed: str = "Business") -> AppError:
    return AppError(
        403,
        "plan_required",
        f"{feature} is available on the {needed} plan and above.",
        {"feature": feature, "min_plan": needed.lower()},
    )


async def apply_plan_constraints(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """After a downgrade, switch off what the new plan doesn't include. Nothing is deleted:
    content, media and memory stay; only features are turned off. Returns what changed."""
    plan = PLANS[effective_plan(await user_subscription(db, user_id))]
    changed: list[str] = []
    workspaces = (
        await db.execute(
            select(Workspace).where(Workspace.owner_id == user_id, Workspace.deleted_at.is_(None))
        )
    ).scalars()
    for ws in workspaces:
        settings = dict(ws.settings or {})
        if not plan.auto_publish and settings.get("approval_required") is False:
            settings["approval_required"] = True
            changed.append(f"{ws.name}: approval required again")
        autopilot = dict(settings.get("autopilot") or {})
        if not plan.autopilot and autopilot.get("enabled"):
            autopilot["enabled"] = False
            settings["autopilot"] = autopilot
            changed.append(f"{ws.name}: autopilot turned off")
        if settings != (ws.settings or {}):
            ws.settings = settings
    return changed
