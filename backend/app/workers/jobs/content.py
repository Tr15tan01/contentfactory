from __future__ import annotations

import uuid
from typing import Any

from app.ai.providers import get_provider
from app.content.service import run_generation
from app.core.database import SessionLocal


async def generate_content(ctx: dict[str, Any], content_id: str, usage_id: str) -> str:
    async with SessionLocal() as db:
        content = await run_generation(
            db, get_provider(), uuid.UUID(content_id), uuid.UUID(usage_id)
        )
        return content.status.value if content else "missing"
