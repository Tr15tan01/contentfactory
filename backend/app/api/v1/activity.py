"""Notifications, notification preferences, and the agent activity timeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.auth.dependencies import DB, CurrentUser, CurrentWorkspace
from app.core.errors import not_found
from app.core.security import utcnow
from app.models import AgentRun, Notification, NotificationPreference, Workspace, WorkspaceMember
from app.models.enums import AgentKind, AgentRunStatus, NotificationType
from app.notifications.service import EMAIL_BY_DEFAULT, LABELS

router = APIRouter(tags=["activity"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    workspace_name: str
    type: NotificationType
    priority: str
    title: str
    body: str | None
    action_url: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    unread: int


class PreferenceOut(BaseModel):
    type: NotificationType
    label: str
    in_app: bool
    email: bool


class PreferenceIn(BaseModel):
    type: NotificationType
    in_app: bool
    email: bool


class StepOut(BaseModel):
    position: int
    kind: str
    title: str
    detail: str | None
    status: AgentRunStatus
    started_at: datetime


class RunOut(BaseModel):
    id: uuid.UUID
    agent: AgentKind
    trigger: str
    status: AgentRunStatus
    goal: str
    summary: str | None
    error: str | None
    steps_taken: int
    cost_usd: float
    started_at: datetime | None
    finished_at: datetime | None
    limits: dict[str, Any]
    steps: list[StepOut]


@router.get("/notifications", response_model=NotificationPage)
async def list_notifications(
    user: CurrentUser,
    db: DB,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> NotificationPage:
    mine = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
    conds = [
        Notification.user_id == user.id,
        Notification.workspace_id.in_(mine),
        Notification.data["in_app"].astext != "false",
    ]
    q = (
        select(Notification, Workspace.name)
        .join(Workspace, Workspace.id == Notification.workspace_id)
        .where(*conds, Workspace.deleted_at.is_(None))
    )
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    rows = (await db.execute(q.order_by(Notification.created_at.desc()).limit(limit))).all()
    unread = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(*conds, Notification.read_at.is_(None))
        )
    ).scalar_one()
    items = [
        NotificationOut.model_validate(
            {
                **{c: getattr(n, c) for c in NotificationOut.model_fields if c != "workspace_name"},
                "workspace_name": name,
            }
        )
        for n, name in rows
    ]
    return NotificationPage(items=items, unread=unread)


@router.post("/notifications/{notification_id}/read", status_code=204)
async def mark_read(notification_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    n = await db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise not_found("Notification")
    n.read_at = n.read_at or utcnow()
    await db.commit()
    return Response(status_code=204)


@router.post("/notifications/read-all", status_code=204)
async def mark_all_read(user: CurrentUser, db: DB) -> Response:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    await db.commit()
    return Response(status_code=204)


@router.get(
    "/workspaces/{workspace_id}/notification-preferences", response_model=list[PreferenceOut]
)
async def get_preferences(ctx: CurrentWorkspace, db: DB) -> list[PreferenceOut]:
    rows = {
        p.type: p
        for p in (
            await db.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == ctx.user.id,
                    NotificationPreference.workspace_id == ctx.workspace.id,
                )
            )
        ).scalars()
    }
    return [
        PreferenceOut(
            type=t,
            label=label,
            in_app=rows[t].in_app if t in rows else True,
            email=rows[t].email if t in rows else t in EMAIL_BY_DEFAULT,
        )
        for t, label in LABELS.items()
    ]


@router.put(
    "/workspaces/{workspace_id}/notification-preferences", response_model=list[PreferenceOut]
)
async def set_preferences(
    body: list[PreferenceIn], ctx: CurrentWorkspace, db: DB
) -> list[PreferenceOut]:
    existing = {
        p.type: p
        for p in (
            await db.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == ctx.user.id,
                    NotificationPreference.workspace_id == ctx.workspace.id,
                )
            )
        ).scalars()
    }
    for item in body:
        if item.type not in LABELS:
            continue
        pref = existing.get(item.type) or NotificationPreference(
            user_id=ctx.user.id, workspace_id=ctx.workspace.id, type=item.type
        )
        pref.in_app, pref.email = item.in_app, item.email
        if item.type not in existing:
            db.add(pref)
    await db.commit()
    return await get_preferences(ctx, db)


@router.get("/workspaces/{workspace_id}/agent/runs", response_model=list[RunOut])
async def agent_runs(
    ctx: CurrentWorkspace,
    db: DB,
    agent: AgentKind | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 40,
) -> list[RunOut]:
    q = (
        select(AgentRun)
        .where(AgentRun.workspace_id == ctx.workspace.id)
        .options(selectinload(AgentRun.steps))
    )
    if agent:
        q = q.where(AgentRun.agent == agent)
    runs = (await db.execute(q.order_by(AgentRun.created_at.desc()).limit(limit))).scalars().all()
    return [
        RunOut(
            id=r.id,
            agent=r.agent,
            trigger=r.trigger.value,
            status=r.status,
            goal=r.goal,
            summary=r.summary,
            error=r.error,
            steps_taken=r.steps_taken,
            cost_usd=float(r.cost_usd or 0),
            started_at=r.started_at,
            finished_at=r.finished_at,
            limits={
                "max_steps": r.max_steps,
                "max_runtime_seconds": r.max_runtime_seconds,
                "max_cost_usd": float(r.max_cost_usd),
            },
            steps=[
                StepOut(
                    position=s.position,
                    kind=s.kind,
                    title=s.title,
                    detail=s.detail,
                    status=s.status,
                    started_at=s.started_at,
                )
                for s in r.steps
            ],
        )
        for r in runs
    ]
