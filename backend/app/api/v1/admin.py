"""Platform administration. Superusers only; every change is audited."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.auth.dependencies import DB, require_superuser
from app.billing.entitlements import effective_plan
from app.billing.plans import PLANS
from app.core.errors import AppError, not_found
from app.core.security import utcnow
from app.models import AIUsage, AuditLog, Publication, Session, Subscription, User, Workspace
from app.models.enums import SubscriptionStatus, UsageStatus
from app.services import audit

router = APIRouter(prefix="/admin", tags=["admin"])
Admin = Annotated[User, Depends(require_superuser)]


class UserRow(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    plan: str
    status: str
    created_at: datetime
    last_login_at: datetime | None
    suspended_reason: str | None
    is_superuser: bool


class SuspendIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.get("/overview")
async def overview(admin: Admin, db: DB) -> dict[str, Any]:
    now = utcnow()
    week, month = now - timedelta(days=7), now - timedelta(days=30)
    subs = (await db.execute(select(Subscription))).scalars().all()
    by_plan: dict[str, int] = {}
    mrr = 0.0
    for s in subs:
        plan = effective_plan(s)
        by_plan[plan.value] = by_plan.get(plan.value, 0) + 1
        if (
            s.paddle_subscription_id
            and s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE)
            and s.manual_plan_override is None
        ):
            mrr += (s.unit_price_cents or PLANS[s.plan].price_usd * 100) / 100
    count = lambda q: db.execute(q)  # noqa: E731
    users = (
        await count(select(func.count()).select_from(User).where(User.deleted_at.is_(None)))
    ).scalar_one()
    signups = (
        await count(select(func.count()).select_from(User).where(User.created_at >= week))
    ).scalar_one()
    workspaces = (
        await count(
            select(func.count())
            .select_from(Workspace)
            .where(Workspace.deleted_at.is_(None), Workspace.is_demo.is_(False))
        )
    ).scalar_one()
    ai = (
        await count(
            select(func.count(), func.coalesce(func.sum(AIUsage.estimated_cost_usd), 0)).where(
                AIUsage.created_at >= month, AIUsage.status == UsageStatus.COMMITTED
            )
        )
    ).one()
    pubs = dict(
        (
            await count(
                select(Publication.status, func.count())
                .where(Publication.created_at >= week)
                .group_by(Publication.status)
            )
        ).all()
    )
    return {
        "users": users,
        "signups_7d": signups,
        "workspaces": workspaces,
        "plans": by_plan,
        "mrr_usd": round(mrr, 2),
        "ai_calls_30d": ai[0],
        "ai_cost_usd_30d": float(ai[1]),
        "publications_7d": {k.value: v for k, v in pubs.items()},
    }


@router.get("/users", response_model=list[UserRow])
async def users(
    admin: Admin,
    db: DB,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[UserRow]:
    stmt = select(User).where(User.deleted_at.is_(None))
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(term), User.full_name.ilike(term)))
    rows = (await db.execute(stmt.order_by(User.created_at.desc()).limit(limit))).scalars().all()
    subs = {
        s.user_id: s
        for s in (
            await db.execute(
                select(Subscription).where(
                    Subscription.user_id.in_([u.id for u in rows] or [uuid.uuid4()])
                )
            )
        ).scalars()
    }
    return [
        UserRow(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            plan=effective_plan(subs.get(u.id)).value,
            status="suspended"
            if u.suspended_at
            else ("active" if u.email_verified_at else "unverified"),
            created_at=u.created_at,
            last_login_at=u.last_login_at,
            suspended_reason=u.suspended_reason,
            is_superuser=u.is_superuser,
        )
        for u in rows
    ]


@router.post("/users/{user_id}/suspend", status_code=204)
async def suspend(user_id: uuid.UUID, body: SuspendIn, admin: Admin, db: DB) -> None:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise not_found("User")
    if user.id == admin.id or user.is_superuser:
        raise AppError(409, "cannot_suspend", "Administrators can't be suspended here.")
    user.suspended_at, user.suspended_reason = utcnow(), body.reason
    # Existing sessions end immediately (every request checks the session row).
    for s in (
        await db.execute(
            select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))
        )
    ).scalars():
        s.revoked_at, s.revoked_reason = utcnow(), "suspended"
    audit.record(
        db,
        "admin.user_suspended",
        actor_user_id=admin.id,
        entity_type="user",
        entity_id=user.id,
        data={"reason": body.reason},
    )
    await db.commit()


@router.post("/users/{user_id}/unsuspend", status_code=204)
async def unsuspend(user_id: uuid.UUID, admin: Admin, db: DB) -> None:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise not_found("User")
    user.suspended_at = user.suspended_reason = None
    audit.record(
        db, "admin.user_unsuspended", actor_user_id=admin.id, entity_type="user", entity_id=user.id
    )
    await db.commit()


@router.get("/audit-log")
async def audit_log(
    admin: Admin,
    db: DB,
    action: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[dict[str, Any]]:
    stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.actor_user_id)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    rows = (await db.execute(stmt.order_by(AuditLog.created_at.desc()).limit(limit))).all()
    return [
        {
            "id": a.id,
            "action": a.action,
            "actor": email,
            "workspace_id": a.workspace_id,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "data": a.data,
            "ip_address": a.ip_address,
            "created_at": a.created_at,
        }
        for a, email in rows
    ]
