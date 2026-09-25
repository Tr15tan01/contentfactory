from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.ai.images import get_image_provider
from app.auth.dependencies import DB, CurrentWorkspace, Queue
from app.core.rate_limit import rate_limit
from app.media import generation
from app.models.enums import MediaKind, WorkspaceRole
from app.schemas.media import (
    BuildVideoIn,
    FolderIn,
    FolderOut,
    GeneratedOut,
    GenerateImageIn,
    MediaOut,
    MediaPageOut,
    MediaUpdateIn,
    TagCount,
    UploadIn,
    UploadOut,
)
from app.services import media as svc
from app.storage import Storage, get_storage

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["media"])
StorageDep = Annotated[Storage, Depends(get_storage)]
EDITORS = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR)


@router.get("/media", response_model=MediaPageOut)
async def list_media(
    ctx: CurrentWorkspace,
    db: DB,
    storage: StorageDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    kind: MediaKind | None = None,
    folder: Annotated[str | None, Query(max_length=40)] = None,
    tag: Annotated[str | None, Query(max_length=64)] = None,
    favorites: bool = False,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = svc.PAGE_SIZE,
) -> MediaPageOut:
    return await svc.list_media(
        db,
        storage,
        ctx.workspace,
        q=q,
        kind=kind,
        folder=folder,
        tag=tag,
        favorites=favorites,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "/media/uploads",
    response_model=UploadOut,
    status_code=201,
    dependencies=[Depends(rate_limit("media_upload", 120, 60))],
)
async def create_upload(
    body: UploadIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> UploadOut:
    ctx.require_role(*EDITORS)
    return await svc.create_upload(db, storage, ctx.workspace, ctx.user.id, body)


@router.post("/media/{asset_id}/complete", response_model=MediaOut)
async def complete_upload(
    asset_id: uuid.UUID, ctx: CurrentWorkspace, db: DB, storage: StorageDep, queue: Queue
) -> MediaOut:
    ctx.require_role(*EDITORS)
    return await svc.complete_upload(db, storage, queue, ctx.workspace, asset_id)


@router.post(
    "/media/generate-image",
    response_model=GeneratedOut,
    status_code=202,
    dependencies=[Depends(rate_limit("ai_image", 10, 60))],
)
async def generate_image(
    body: GenerateImageIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep, queue: Queue
) -> GeneratedOut:
    ctx.require_role(*EDITORS)
    asset, reused = await generation.start_image(
        db,
        ctx.workspace,
        ctx.user,
        prompt=body.prompt,
        aspect=body.aspect,
        use_brand=body.use_brand,
        content_id=body.content_id,
        queue=queue,
        provider=get_image_provider(),
        storage=storage,
    )
    await db.refresh(asset)
    return GeneratedOut(asset=svc.to_out(asset, storage), reused=reused, credits=0 if reused else 1)


@router.post(
    "/media/build-video",
    response_model=GeneratedOut,
    status_code=202,
    dependencies=[Depends(rate_limit("video_build", 5, 60))],
)
async def build_video(
    body: BuildVideoIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep, queue: Queue
) -> GeneratedOut:
    ctx.require_role(*EDITORS)
    asset, reused = await generation.start_video(
        db,
        ctx.workspace,
        ctx.user,
        scenes=[s.model_dump() for s in body.scenes],
        aspect=body.aspect,
        title=body.title,
        content_id=body.content_id,
        queue=queue,
        storage=storage,
    )
    await db.refresh(asset)
    credits = 0 if reused else generation.video_credits(sum(s.duration_s for s in body.scenes))
    return GeneratedOut(asset=svc.to_out(asset, storage), reused=reused, credits=credits)


@router.get("/media/tags", response_model=list[TagCount])
async def tags(ctx: CurrentWorkspace, db: DB) -> list[TagCount]:
    return await svc.tag_counts(db, ctx.workspace)


@router.get("/media/{asset_id}", response_model=MediaOut)
async def get_media(
    asset_id: uuid.UUID, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> MediaOut:
    return svc.to_out(await svc.get_asset(db, ctx.workspace, asset_id), storage)


@router.patch("/media/{asset_id}", response_model=MediaOut)
async def update_media(
    asset_id: uuid.UUID, body: MediaUpdateIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> MediaOut:
    ctx.require_role(*EDITORS)
    return await svc.update_media(db, storage, ctx.workspace, asset_id, body)


@router.delete("/media/{asset_id}", status_code=204)
async def delete_media(
    asset_id: uuid.UUID, ctx: CurrentWorkspace, db: DB, queue: Queue
) -> Response:
    ctx.require_role(*EDITORS)
    await svc.delete_media(db, queue, ctx.workspace, ctx.user.id, asset_id)
    return Response(status_code=204)


@router.get("/media-folders", response_model=list[FolderOut])
async def list_folders(ctx: CurrentWorkspace, db: DB) -> list[FolderOut]:
    return await svc.list_folders(db, ctx.workspace)


@router.post("/media-folders", response_model=FolderOut, status_code=201)
async def create_folder(body: FolderIn, ctx: CurrentWorkspace, db: DB) -> FolderOut:
    ctx.require_role(*EDITORS)
    return await svc.create_folder(db, ctx.workspace, body.name)


@router.patch("/media-folders/{folder_id}", response_model=FolderOut)
async def rename_folder(
    folder_id: uuid.UUID, body: FolderIn, ctx: CurrentWorkspace, db: DB
) -> FolderOut:
    ctx.require_role(*EDITORS)
    return await svc.rename_folder(db, ctx.workspace, folder_id, body.name)


@router.delete("/media-folders/{folder_id}", status_code=204)
async def delete_folder(folder_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> Response:
    ctx.require_role(*EDITORS)
    await svc.delete_folder(db, ctx.workspace, folder_id)
    return Response(status_code=204)
