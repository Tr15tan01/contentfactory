from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import ACCESS_COOKIE
from app.core.database import get_db
from app.core.errors import forbidden, not_found, unauthorized
from app.core.security import decode_access_token, utcnow
from app.models import Session, User, Workspace, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.repositories import workspaces as ws_repo
from app.workers.queue import JobQueue, get_queue

DB = Annotated[AsyncSession, Depends(get_db)]
Queue = Annotated[JobQueue, Depends(get_queue)]


@dataclass
class AuthContext:
    user: User
    session: Session


async def get_auth_context(request: Request, db: DB) -> AuthContext:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise unauthorized()
    payload = decode_access_token(token)
    if payload is None:
        raise unauthorized("Your session expired.", code="session_expired")
    try:
        user_id, session_id = uuid.UUID(payload["sub"]), uuid.UUID(payload["sid"])
    except (KeyError, ValueError):
        raise unauthorized() from None

    # One indexed lookup: revocation takes effect immediately, not at token expiry.
    row = (
        await db.execute(
            select(User, Session)
            .join(Session, Session.user_id == User.id)
            .where(Session.id == session_id, User.id == user_id)
        )
    ).first()
    if row is None:
        raise unauthorized("Your session expired.", code="session_expired")
    user, session = row
    if (
        session.revoked_at
        or session.expires_at <= utcnow()
        or user.deleted_at
        or not user.is_active
        or user.suspended_at
    ):
        raise unauthorized("Your session ended. Sign in again.", code="session_expired")
    return AuthContext(user=user, session=session)


CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


async def get_current_user(ctx: CurrentAuth) -> User:
    return ctx.user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_superuser(user: CurrentUser) -> User:
    if not user.is_superuser:
        raise forbidden()
    return user


@dataclass
class WorkspaceContext:
    workspace: Workspace
    member: WorkspaceMember
    user: User

    def require_role(self, *roles: WorkspaceRole) -> None:
        if self.member.role not in roles:
            raise forbidden("Your role in this workspace can't do that.")


async def get_workspace_context(
    user: CurrentUser,
    db: DB,
    workspace_id: Annotated[uuid.UUID, Path()],
) -> WorkspaceContext:
    """Authorization gate for every workspace-scoped route. Non-members get 404 so that
    workspace IDs can't be probed."""
    found = await ws_repo.get_membership(db, workspace_id, user.id)
    if found is None:
        raise not_found("Workspace")
    workspace, member = found
    return WorkspaceContext(workspace=workspace, member=member, user=user)


CurrentWorkspace = Annotated[WorkspaceContext, Depends(get_workspace_context)]
