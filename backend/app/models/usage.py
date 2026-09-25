from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk, enum_type, jsonb_default
from app.models.enums import AIOperation, UsageStatus


class AIUsage(UUIDPk, Base):
    """Every AI call, reserved before it runs and committed/refunded after. Failed generations
    are refunded, so "your credit was not consumed" is literally true."""

    __tablename__ = "ai_usage"
    __table_args__ = (
        Index("ix_ai_usage_ws_op_time", "workspace_id", "operation", "created_at"),
        Index("ix_ai_usage_user_time", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    operation: Mapped[AIOperation] = mapped_column(enum_type(AIOperation))
    status: Mapped[UsageStatus] = mapped_column(enum_type(UsageStatus), index=True)
    provider: Mapped[str] = mapped_column(String(48))
    model: Mapped[str] = mapped_column(String(120))
    input_units: Mapped[int | None]
    output_units: Mapped[int | None]
    unit_kind: Mapped[str] = mapped_column(String(16), server_default="tokens")
    credits: Mapped[int] = mapped_column(server_default="1")
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), server_default="0")
    cache_hit: Mapped[bool] = mapped_column(server_default="false")
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contents.id", ondelete="SET NULL")
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    finalized_at: Mapped[datetime | None]
    # Hash of operation + model + normalised prompt. Identical requests reuse a cached result.
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)


class AIResponseCache(UUIDPk, Base):
    """Stored AI results keyed by request fingerprint, per workspace. A repeated identical
    request returns this instead of calling (and charging for) the provider again."""

    __tablename__ = "ai_response_cache"
    __table_args__ = (UniqueConstraint("workspace_id", "fingerprint", name="uq_ai_cache_ws_fp"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(48))
    model: Mapped[str] = mapped_column(String(120))
    response: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True)
