from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.request_context import client_ip_for_storage, user_agent
from app.models import AuditLog


def record(
    db: AsyncSession,
    action: str,
    *,
    actor_user_id: uuid.UUID | None = None,
    workspace_id: uuid.UUID | None = None,
    request: Request | None = None,
    entity_type: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Stage an audit row in the caller's transaction (committed with the change it records)."""
    db.add(
        AuditLog(
            action=action,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            ip_address=client_ip_for_storage(request) if request else None,
            user_agent=user_agent(request) if request else None,
            data=data or {},
        )
    )
