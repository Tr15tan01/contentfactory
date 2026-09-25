from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.auth.dependencies import DB, CurrentUser, CurrentWorkspace
from app.models import BusinessProfile, Workspace
from app.models.enums import WorkspaceRole
from app.repositories import workspaces as ws_repo
from app.schemas.workspace import DashboardOut, WorkspaceOut, WorkspaceUpdateIn
from app.services import audit
from app.services.dashboard import build_dashboard

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


async def _out(db: DB, ws: Workspace, role: WorkspaceRole) -> WorkspaceOut:
    completed = (
        await db.execute(
            select(BusinessProfile.onboarding_completed_at).where(
                BusinessProfile.workspace_id == ws.id
            )
        )
    ).scalar_one_or_none()
    return WorkspaceOut(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        role=role,
        timezone=ws.timezone,
        is_demo=ws.is_demo,
        onboarding_completed=completed is not None,
        settings=ws.settings,
    )


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(user: CurrentUser, db: DB) -> list[WorkspaceOut]:
    return [await _out(db, ws, role) for ws, role in await ws_repo.list_for_user(db, user.id)]


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(ctx: CurrentWorkspace, db: DB) -> WorkspaceOut:
    return await _out(db, ctx.workspace, ctx.member.role)


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(body: WorkspaceUpdateIn, ctx: CurrentWorkspace, db: DB) -> WorkspaceOut:
    ctx.require_role(WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
    changes = body.model_dump(exclude_none=True)
    for key, value in changes.items():
        setattr(ctx.workspace, key, value)
    audit.record(
        db,
        "workspace.updated",
        actor_user_id=ctx.user.id,
        workspace_id=ctx.workspace.id,
        data=changes,
    )
    await db.commit()
    return await _out(db, ctx.workspace, ctx.member.role)


@router.get("/{workspace_id}/dashboard", response_model=DashboardOut)
async def dashboard(ctx: CurrentWorkspace, db: DB) -> DashboardOut:
    return await build_dashboard(db, ctx.workspace)
