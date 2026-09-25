from __future__ import annotations

import uuid
from typing import Any

from app.core.database import SessionLocal
from app.social import publisher
from app.social.service import refresh_due_tokens
from app.workers.queue import get_queue


async def enqueue_due_publications(ctx: dict[str, Any]) -> dict[str, int]:
    async with SessionLocal() as db:
        return await publisher.enqueue_due(db, get_queue())


async def publish_publication(ctx: dict[str, Any], publication_id: str) -> str:
    async with SessionLocal() as db:
        status = await publisher.publish(db, get_queue(), uuid.UUID(publication_id))
        return status.value if status else "missing"


async def refresh_social_tokens(ctx: dict[str, Any]) -> dict[str, int]:
    async with SessionLocal() as db:
        return await refresh_due_tokens(db)
