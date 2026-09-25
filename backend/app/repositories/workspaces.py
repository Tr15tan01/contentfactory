from __future__ import annotations

import re
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole

DEFAULT_WORKSPACE_SETTINGS = {
    "prefer_media": "when_relevant",  # always | when_relevant | never
    "approval_required": True,
    "reminder_offsets_hours": [24],  # 24, 6, 1 or [] for none
    "autopilot": {
        "enabled": False,
        "daily_limit": 2,
        "monthly_limit": 40,
        "allowed_platforms": [],
        "allowed_content_types": [],
        "blocked_topics": [],
    },
}


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "workspace"
    return f"{base}-{secrets.token_hex(3)}"


async def create_workspace(db: AsyncSession, owner_id: uuid.UUID, name: str) -> Workspace:
    ws = Workspace(
        name=name, slug=slugify(name), owner_id=owner_id, settings=DEFAULT_WORKSPACE_SETTINGS
    )
    db.add(ws)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner_id, role=WorkspaceRole.OWNER))
    await db.flush()
    return ws


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Workspace, WorkspaceRole]]:
    stmt = (
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user_id, Workspace.deleted_at.is_(None))
        .order_by(Workspace.created_at)
    )
    return [(w, r) for w, r in (await db.execute(stmt)).all()]


async def get_membership(
    db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Workspace, WorkspaceMember] | None:
    stmt = (
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            Workspace.id == workspace_id,
            WorkspaceMember.user_id == user_id,
            Workspace.deleted_at.is_(None),
        )
    )
    row = (await db.execute(stmt)).first()
    return (row[0], row[1]) if row else None
