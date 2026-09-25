"""In-app notifications with optional email, deduplicated so nobody is told the same thing twice."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models import Notification, NotificationPreference, User, WorkspaceMember
from app.models.enums import NotificationType, WorkspaceRole

# Emailed unless the user turns them off; everything else is in-app only by default.
EMAIL_BY_DEFAULT = {
    NotificationType.PRE_PUBLISH_REMINDER,
    NotificationType.APPROVAL_OVERDUE,
    NotificationType.POST_FAILED,
    NotificationType.ACCOUNT_DISCONNECTED,
    NotificationType.QUOTA_WARNING,
    NotificationType.PAYMENT_ISSUE,
}
LABELS = {
    NotificationType.PRE_PUBLISH_REMINDER: "Posts waiting for approval",
    NotificationType.APPROVAL_OVERDUE: "Missed approvals",
    NotificationType.POST_PUBLISHED: "Posts published",
    NotificationType.POST_FAILED: "Posts that failed to publish",
    NotificationType.ACCOUNT_DISCONNECTED: "Accounts that need reconnecting",
    NotificationType.ANALYTICS_INSIGHT: "New insights",
    NotificationType.EXPERIMENT_RESULT: "Experiment results",
    NotificationType.QUOTA_WARNING: "Allowance running low",
    NotificationType.PAYMENT_ISSUE: "Payment problems",
}
ACTIONABLE_ROLES = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR)


async def _recipients(
    db: AsyncSession, workspace_id: uuid.UUID, roles: tuple[WorkspaceRole, ...]
) -> list[User]:
    rows = await db.execute(
        select(User)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role.in_(roles),
            User.deleted_at.is_(None),
            User.suspended_at.is_(None),
        )
    )
    return list(rows.scalars())


async def _prefs(
    db: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID, kind: NotificationType
) -> tuple[bool, bool]:
    pref = (
        await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.workspace_id == workspace_id,
                NotificationPreference.type == kind,
            )
        )
    ).scalar_one_or_none()
    if pref is None:
        return True, kind in EMAIL_BY_DEFAULT
    return pref.in_app, pref.email


async def notify(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    kind: NotificationType,
    title: str,
    body: str | None = None,
    action_url: str | None = None,
    dedupe: str | None = None,
    priority: str = "normal",
    roles: tuple[WorkspaceRole, ...] = ACTIONABLE_ROLES,
    entity: tuple[str, uuid.UUID] | None = None,
    data: dict[str, Any] | None = None,
) -> int:
    """Create one notification per recipient, skipping duplicates by `dedupe`. Commits nothing:
    the caller's transaction decides. Emails go out from the `send_pending_emails` job, so a
    rolled-back transaction never sends anything."""
    created = 0
    for user in await _recipients(db, workspace_id, roles):
        in_app, email = await _prefs(db, user.id, workspace_id, kind)
        if not (in_app or email):
            continue
        key = f"{workspace_id}:{user.id}:{dedupe}" if dedupe else None
        stmt = insert(Notification).values(
            workspace_id=workspace_id,
            user_id=user.id,
            type=kind,
            priority=priority,
            title=title[:200],
            body=body,
            action_url=action_url,
            entity_type=entity[0] if entity else None,
            entity_id=entity[1] if entity else None,
            data={**(data or {}), "email": email, "in_app": in_app},
            dedupe_key=key,
            read_at=None if in_app else utcnow(),
        )
        new_id = (
            await db.execute(
                stmt.on_conflict_do_nothing(index_elements=["dedupe_key"]).returning(
                    Notification.id
                )
            )
        ).scalar_one_or_none()
        if new_id is None:
            continue
        created += 1
    return created


async def send_pending_emails(db: AsyncSession, limit: int = 100) -> int:
    """Every minute: email notifications that asked for it and haven't been sent (last 24 h).
    Runs after the creating transaction committed, so a rolled-back change never emails."""
    from datetime import timedelta

    from app.notifications.email import providers
    from app.notifications.email.templates import render

    rows = (
        await db.execute(
            select(Notification, User)
            .join(User, User.id == Notification.user_id)
            .where(
                Notification.emailed_at.is_(None),
                Notification.data["email"].astext == "true",
                Notification.created_at > utcnow() - timedelta(hours=24),
                User.deleted_at.is_(None),
            )
            .order_by(Notification.created_at)
            .limit(limit)
            .with_for_update(of=Notification, skip_locked=True)
        )
    ).all()
    provider = providers.get_email_provider()
    sent = 0
    for n, user in rows:
        params = {
            "name": user.full_name,
            "title": n.title,
            "body": n.body,
            "action_url": n.action_url,
        }
        await provider.send(render("notification", user.email, params))
        n.emailed_at = utcnow()
        sent += 1
    await db.commit()
    return sent
