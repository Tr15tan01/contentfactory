from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.ai import usage as ai_usage
from app.ai.base import AIProvider
from app.ai.images import get_image_provider
from app.ai.providers import get_provider
from app.auth.dependencies import DB, CurrentWorkspace, Queue
from app.content import service as svc
from app.core.rate_limit import rate_limit
from app.models.enums import ContentStatus, Platform, WorkspaceRole
from app.schemas.content import (
    ContentOut,
    ContentPage,
    CreateIn,
    GenerateIn,
    RegenerateIn,
    RejectIn,
    ScheduleIn,
    UpdateIn,
    UsageOut,
    VersionOut,
)
from app.storage import Storage, get_storage

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["content"])
StorageDep = Annotated[Storage, Depends(get_storage)]
ProviderDep = Annotated[AIProvider, Depends(get_provider)]
EDITORS = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR)


@router.get("/usage", response_model=UsageOut)
async def usage(ctx: CurrentWorkspace, db: DB, provider: ProviderDep) -> UsageOut:
    return UsageOut.model_validate(
        {
            **await ai_usage.summary(db, ctx.workspace),
            "ai_provider": provider.name,
            "image_provider": get_image_provider().name,
            "video_builder": shutil.which("ffmpeg") is not None,
        }
    )


@router.get("/content", response_model=ContentPage)
async def list_content(
    ctx: CurrentWorkspace,
    db: DB,
    storage: StorageDep,
    status: Annotated[list[ContentStatus] | None, Query()] = None,
    platform: Platform | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    unscheduled: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ContentPage:
    return await svc.list_content(
        db,
        storage,
        ctx.workspace,
        status=status,
        platform=platform,
        start=start,
        end=end,
        unscheduled=unscheduled,
        q=q,
        limit=limit,
    )


@router.post(
    "/content/generate",
    response_model=ContentOut,
    status_code=202,
    dependencies=[Depends(rate_limit("ai_generate", 30, 60))],
)
async def generate(
    body: GenerateIn,
    ctx: CurrentWorkspace,
    db: DB,
    storage: StorageDep,
    queue: Queue,
    provider: ProviderDep,
) -> ContentOut:
    ctx.require_role(*EDITORS)
    content = await svc.start_generation(db, ctx.workspace, ctx.user, body, queue, provider)
    return await svc.serialize(db, storage, content)


@router.post("/content", response_model=ContentOut, status_code=201)
async def create(body: CreateIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep) -> ContentOut:
    ctx.require_role(*EDITORS)
    return await svc.serialize(
        db, storage, await svc.create_manual(db, ctx.workspace, ctx.user, body)
    )


@router.get("/content/{content_id}", response_model=ContentOut)
async def get(
    content_id: uuid.UUID, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ContentOut:
    return await svc.serialize(db, storage, await svc.get_content(db, ctx.workspace, content_id))


@router.patch("/content/{content_id}", response_model=ContentOut)
async def update(
    content_id: uuid.UUID, body: UpdateIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ContentOut:
    ctx.require_role(*EDITORS)
    return await svc.serialize(
        db, storage, await svc.update(db, ctx.workspace, ctx.user, content_id, body)
    )


@router.post(
    "/content/{content_id}/regenerate",
    response_model=ContentOut,
    status_code=202,
    dependencies=[Depends(rate_limit("ai_generate", 30, 60))],
)
async def regenerate(
    content_id: uuid.UUID,
    body: RegenerateIn,
    ctx: CurrentWorkspace,
    db: DB,
    storage: StorageDep,
    queue: Queue,
    provider: ProviderDep,
) -> ContentOut:
    ctx.require_role(*EDITORS)
    content = await svc.regenerate(
        db, ctx.workspace, ctx.user, content_id, body.instruction, queue, provider
    )
    return await svc.serialize(db, storage, content)


@router.post("/content/{content_id}/submit", response_model=ContentOut)
async def submit(
    content_id: uuid.UUID, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ContentOut:
    ctx.require_role(*EDITORS)
    return await svc.serialize(
        db, storage, await svc.submit(db, ctx.workspace, ctx.user, content_id)
    )


@router.post("/content/{content_id}/approve", response_model=ContentOut)
async def approve(
    content_id: uuid.UUID, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ContentOut:
    ctx.require_role(*EDITORS)
    return await svc.serialize(
        db, storage, await svc.approve(db, ctx.workspace, ctx.user, content_id)
    )


@router.post("/content/{content_id}/reject", response_model=ContentOut)
async def reject(
    content_id: uuid.UUID, body: RejectIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ContentOut:
    ctx.require_role(*EDITORS)
    return await svc.serialize(
        db, storage, await svc.reject(db, ctx.workspace, ctx.user, content_id, body.reason)
    )


@router.put("/content/{content_id}/schedule", response_model=ContentOut)
async def schedule(
    content_id: uuid.UUID, body: ScheduleIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ContentOut:
    ctx.require_role(*EDITORS)
    return await svc.serialize(
        db, storage, await svc.schedule(db, ctx.workspace, ctx.user, content_id, body.scheduled_at)
    )


@router.delete("/content/{content_id}/schedule", response_model=ContentOut)
async def unschedule(
    content_id: uuid.UUID, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ContentOut:
    ctx.require_role(*EDITORS)
    return await svc.serialize(db, storage, await svc.unschedule(db, ctx.workspace, content_id))


@router.post("/content/{content_id}/duplicate", response_model=ContentOut, status_code=201)
async def duplicate(
    content_id: uuid.UUID, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ContentOut:
    ctx.require_role(*EDITORS)
    return await svc.serialize(
        db, storage, await svc.duplicate(db, ctx.workspace, ctx.user, content_id)
    )


@router.delete("/content/{content_id}", status_code=204)
async def delete(content_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> Response:
    ctx.require_role(*EDITORS)
    await svc.remove(db, ctx.workspace, ctx.user, content_id)
    return Response(status_code=204)


@router.get("/content/{content_id}/versions", response_model=list[VersionOut])
async def versions(content_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> list[VersionOut]:
    return await svc.versions(db, ctx.workspace, content_id)


@router.post("/content/{content_id}/versions/{version}/restore", response_model=ContentOut)
async def restore(
    content_id: uuid.UUID, version: int, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ContentOut:
    ctx.require_role(*EDITORS)
    return await svc.serialize(
        db, storage, await svc.restore(db, ctx.workspace, ctx.user, content_id, version)
    )
