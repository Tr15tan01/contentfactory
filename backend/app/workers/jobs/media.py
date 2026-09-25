from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import utcnow
from app.media.processing import process_asset
from app.models import MediaAsset
from app.models.enums import MediaStatus
from app.storage import get_storage

log = logging.getLogger("contentfactory.media")


async def process_media(ctx: dict[str, Any], asset_id: str) -> str:
    async with SessionLocal() as db:
        asset = await process_asset(db, get_storage(), uuid.UUID(asset_id))
        return asset.status.value if asset else "missing"


async def delete_media_objects(ctx: dict[str, Any], keys: list[str]) -> int:
    storage = get_storage()
    for key in keys:
        await storage.delete(key)
    return len(keys)


async def purge_abandoned_uploads(ctx: dict[str, Any]) -> int:
    """Nightly: uploads started but never completed within 24 hours are removed."""
    storage = get_storage()
    cutoff = utcnow() - timedelta(hours=24)
    async with SessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(MediaAsset).where(
                        MediaAsset.status == MediaStatus.PENDING_UPLOAD,
                        MediaAsset.created_at < cutoff,
                    )
                )
            )
            .scalars()
            .all()
        )
        for asset in rows:
            await storage.delete(asset.storage_key)
            await db.delete(asset)
        await db.commit()
    log.info("purged %d abandoned uploads", len(rows))
    return len(rows)


async def generate_image(ctx: dict[str, Any], asset_id: str, usage_id: str) -> str:
    from app.ai.images import get_image_provider
    from app.media.generation import run_image

    async with SessionLocal() as db:
        asset = await run_image(
            db, get_storage(), get_image_provider(), uuid.UUID(asset_id), uuid.UUID(usage_id)
        )
        return asset.status.value if asset else "missing"


async def render_video(ctx: dict[str, Any], asset_id: str, usage_id: str) -> str:
    from app.media.generation import run_video

    async with SessionLocal() as db:
        asset = await run_video(db, get_storage(), uuid.UUID(asset_id), uuid.UUID(usage_id))
        return asset.status.value if asset else "missing"
