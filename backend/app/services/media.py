"""Media library: upload handshake, listing/search, edits, folders, tags, deletion."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.core.security import utcnow
from app.media import policy
from app.models import MediaAsset, MediaFolder, Workspace
from app.models.enums import MediaKind, MediaSource, MediaStatus
from app.schemas.media import (
    FolderOut,
    MediaOut,
    MediaPageOut,
    MediaUpdateIn,
    TagCount,
    UploadIn,
    UploadOut,
    UploadTargetOut,
)
from app.services import audit
from app.storage import Storage
from app.workers.queue import JobQueue

PAGE_SIZE = 40


def to_out(asset: MediaAsset, storage: Storage) -> MediaOut:
    ready = asset.status is MediaStatus.READY
    meta = asset.ai_metadata or {}
    dup = meta.get("duplicate_of")
    return MediaOut(
        id=asset.id,
        kind=asset.kind,
        source=asset.source,
        status=asset.status,
        display_name=asset.display_name,
        original_filename=asset.original_filename,
        description=asset.alt_text,
        tags=list(asset.tags or []),
        folder_id=asset.folder_id,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        width=asset.width,
        height=asset.height,
        duration_seconds=float(asset.duration_seconds)
        if asset.duration_seconds is not None
        else None,
        is_favorite=asset.is_favorite,
        url=storage.download_url(asset.storage_key) if ready else None,
        thumbnail_url=storage.download_url(asset.thumbnail_key)
        if ready and asset.thumbnail_key
        else None,
        duplicate_of=uuid.UUID(dup) if dup else None,
        error=meta.get("error"),
        generator=meta.get("provider") if asset.source is MediaSource.AI_GENERATED else None,
        created_at=asset.created_at,
    )


async def _folder(db: AsyncSession, ws: Workspace, folder_id: uuid.UUID) -> MediaFolder:
    folder = await db.get(MediaFolder, folder_id)
    if folder is None or folder.workspace_id != ws.id or folder.deleted_at is not None:
        raise not_found("Folder")
    return folder


async def get_asset(db: AsyncSession, ws: Workspace, asset_id: uuid.UUID) -> MediaAsset:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.workspace_id != ws.id or asset.deleted_at is not None:
        raise not_found("Media")
    return asset


async def create_upload(
    db: AsyncSession, storage: Storage, ws: Workspace, user_id: uuid.UUID, body: UploadIn
) -> UploadOut:
    media_type = policy.ALLOWED.get(body.content_type.lower())
    if media_type is None:
        raise AppError(
            415,
            "unsupported_media_type",
            "Upload JPEG, PNG, WebP or GIF images, or MP4, MOV or WebM videos.",
        )
    limit = policy.max_bytes(media_type.kind)
    if body.size_bytes > limit:
        raise AppError(
            413,
            "file_too_large",
            f"{media_type.kind.value.capitalize()}s can be up to {limit // (1024 * 1024)} MB.",
            {"max_bytes": limit},
        )
    if body.folder_id:
        await _folder(db, ws, body.folder_id)

    asset_id = uuid.uuid4()
    key = (
        f"workspaces/{ws.id}/media/{asset_id}/{policy.safe_filename(body.filename, media_type.ext)}"
    )
    asset = MediaAsset(
        id=asset_id,
        workspace_id=ws.id,
        folder_id=body.folder_id,
        uploaded_by_id=user_id,
        kind=media_type.kind,
        source=MediaSource.UPLOAD,
        status=MediaStatus.PENDING_UPLOAD,
        storage_bucket=storage.bucket,
        storage_key=key,
        mime_type=media_type.mime,
        size_bytes=body.size_bytes,
        original_filename=body.filename[:255],
        display_name=policy.display_name(body.filename),
        tags=[],
        ai_metadata={},
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    target = storage.upload_target(key, media_type.mime, limit)
    return UploadOut(
        asset=to_out(asset, storage),
        upload=UploadTargetOut(
            url=target.url, method=target.method, fields=target.fields, headers=target.headers
        ),
    )


async def complete_upload(
    db: AsyncSession, storage: Storage, queue: JobQueue, ws: Workspace, asset_id: uuid.UUID
) -> MediaOut:
    asset = await get_asset(db, ws, asset_id)
    if asset.status is not MediaStatus.PENDING_UPLOAD:
        return to_out(asset, storage)  # idempotent: a retried "complete" is harmless
    info = await storage.head(asset.storage_key)
    if info is None:
        raise AppError(409, "upload_missing", "The file hasn't finished uploading. Try again.")
    if info.size_bytes > policy.max_bytes(asset.kind):
        await storage.delete(asset.storage_key)
        raise AppError(413, "file_too_large", "The uploaded file is larger than allowed.")
    asset.size_bytes = info.size_bytes
    asset.status = MediaStatus.PROCESSING
    await db.commit()
    await queue.enqueue("process_media", asset_id=str(asset.id))
    return to_out(asset, storage)


def _encode_cursor(created_at: datetime, asset_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{asset_id}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        ts, _, aid = base64.urlsafe_b64decode(cursor.encode()).decode().partition("|")
        return datetime.fromisoformat(ts), uuid.UUID(aid)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AppError(400, "invalid_cursor", "The page link is invalid.") from exc


async def list_media(
    db: AsyncSession,
    storage: Storage,
    ws: Workspace,
    *,
    q: str | None = None,
    kind: MediaKind | None = None,
    folder: str | None = None,
    tag: str | None = None,
    favorites: bool = False,
    cursor: str | None = None,
    limit: int = PAGE_SIZE,
) -> MediaPageOut:
    # Hide uploads that never finished; show processing/failed so users see what happened.
    conds = [
        MediaAsset.workspace_id == ws.id,
        MediaAsset.deleted_at.is_(None),
        MediaAsset.status != MediaStatus.PENDING_UPLOAD,
    ]
    if kind:
        conds.append(MediaAsset.kind == kind)
    if folder == "unfiled":
        conds.append(MediaAsset.folder_id.is_(None))
    elif folder:
        try:
            conds.append(MediaAsset.folder_id == uuid.UUID(folder))
        except ValueError as exc:
            raise not_found("Folder") from exc
    if tag:
        conds.append(MediaAsset.tags.contains([tag.lower()]))
    if favorites:
        conds.append(MediaAsset.is_favorite.is_(True))
    if q and q.strip():
        term = f"%{q.strip().replace('%', r'\%').replace('_', r'\_')}%"
        conds.append(
            or_(
                MediaAsset.display_name.ilike(term),
                MediaAsset.alt_text.ilike(term),
                MediaAsset.original_filename.ilike(term),
                func.array_to_string(MediaAsset.tags, " ").ilike(term),
            )
        )
    total = (await db.execute(select(func.count()).where(*conds))).scalar_one()
    page_conds = list(conds)
    if cursor:
        ts, aid = _decode_cursor(cursor)
        page_conds.append(
            or_(MediaAsset.created_at < ts, and_(MediaAsset.created_at == ts, MediaAsset.id < aid))
        )
    rows = (
        (
            await db.execute(
                select(MediaAsset)
                .where(*page_conds)
                .order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc())
                .limit(limit + 1)
            )
        )
        .scalars()
        .all()
    )
    items = rows[:limit]
    next_cursor = _encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None
    return MediaPageOut(
        items=[to_out(a, storage) for a in items], next_cursor=next_cursor, total=total
    )


async def update_media(
    db: AsyncSession, storage: Storage, ws: Workspace, asset_id: uuid.UUID, body: MediaUpdateIn
) -> MediaOut:
    asset = await get_asset(db, ws, asset_id)
    if body.display_name is not None:
        asset.display_name = body.display_name.strip()
    if body.description is not None:
        asset.alt_text = body.description.strip() or None
    if body.tags is not None:
        asset.tags = policy.normalize_tags(body.tags)
    if body.move_to_unfiled:
        asset.folder_id = None
    elif body.folder_id is not None:
        asset.folder_id = (await _folder(db, ws, body.folder_id)).id
    if body.is_favorite is not None:
        asset.is_favorite = body.is_favorite
    await db.commit()
    await db.refresh(asset)
    return to_out(asset, storage)


async def delete_media(
    db: AsyncSession, queue: JobQueue, ws: Workspace, user_id: uuid.UUID, asset_id: uuid.UUID
) -> None:
    asset = await get_asset(db, ws, asset_id)
    asset.deleted_at = utcnow()
    audit.record(
        db,
        "media.deleted",
        actor_user_id=user_id,
        workspace_id=ws.id,
        data={"asset_id": str(asset.id), "name": asset.display_name},
    )
    await db.commit()
    keys = [k for k in (asset.storage_key, asset.thumbnail_key) if k]
    await queue.enqueue("delete_media_objects", keys=keys)


async def list_folders(db: AsyncSession, ws: Workspace) -> list[FolderOut]:
    count = (
        select(func.count(MediaAsset.id))
        .where(
            MediaAsset.folder_id == MediaFolder.id,
            MediaAsset.deleted_at.is_(None),
            MediaAsset.status != MediaStatus.PENDING_UPLOAD,
        )
        .scalar_subquery()
    )
    rows = await db.execute(
        select(MediaFolder.id, MediaFolder.name, count)
        .where(MediaFolder.workspace_id == ws.id, MediaFolder.deleted_at.is_(None))
        .order_by(func.lower(MediaFolder.name))
    )
    return [FolderOut(id=i, name=n, asset_count=c) for i, n, c in rows.all()]


async def create_folder(db: AsyncSession, ws: Workspace, name: str) -> FolderOut:
    name = name.strip()
    exists = (
        await db.execute(
            select(MediaFolder.id).where(
                MediaFolder.workspace_id == ws.id,
                MediaFolder.deleted_at.is_(None),
                func.lower(MediaFolder.name) == name.lower(),
            )
        )
    ).first()
    if exists:
        raise AppError(409, "folder_exists", "A folder with that name already exists.")
    folder = MediaFolder(workspace_id=ws.id, name=name)
    db.add(folder)
    await db.commit()
    return FolderOut(id=folder.id, name=folder.name, asset_count=0)


async def rename_folder(
    db: AsyncSession, ws: Workspace, folder_id: uuid.UUID, name: str
) -> FolderOut:
    folder = await _folder(db, ws, folder_id)
    folder.name = name.strip()
    await db.commit()
    return next(f for f in await list_folders(db, ws) if f.id == folder.id)


async def delete_folder(db: AsyncSession, ws: Workspace, folder_id: uuid.UUID) -> None:
    """Deleting a folder never deletes media: its files move to Unfiled."""
    folder = await _folder(db, ws, folder_id)
    await db.execute(
        update(MediaAsset).where(MediaAsset.folder_id == folder.id).values(folder_id=None)
    )
    folder.deleted_at = utcnow()
    await db.commit()


async def tag_counts(db: AsyncSession, ws: Workspace) -> list[TagCount]:
    tag = func.unnest(MediaAsset.tags).label("tag")
    sub = (
        select(tag)
        .where(MediaAsset.workspace_id == ws.id, MediaAsset.deleted_at.is_(None))
        .subquery()
    )
    rows = await db.execute(
        select(sub.c.tag, func.count())
        .group_by(sub.c.tag)
        .order_by(func.count().desc(), sub.c.tag)
        .limit(50)
    )
    return [TagCount(tag=t, count=c) for t, c in rows.all()]
