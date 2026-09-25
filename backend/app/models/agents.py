from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk, enum_type, jsonb_default
from app.models.enums import AgentKind, AgentRunStatus, AgentTrigger


class AgentRun(UUIDPk, Timestamps, Base):
    """A bounded unit of agent work. Limits are copied onto the run when it starts so a
    config change can't unbound a run that's already going."""

    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_ws_status", "workspace_id", "status"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True
    )
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    agent: Mapped[AgentKind] = mapped_column(enum_type(AgentKind), index=True)
    trigger: Mapped[AgentTrigger] = mapped_column(enum_type(AgentTrigger))
    status: Mapped[AgentRunStatus] = mapped_column(enum_type(AgentRunStatus), index=True)
    goal: Mapped[str] = mapped_column(String(300))  # user-facing: "Plan next week's content"
    summary: Mapped[str | None] = mapped_column(Text)

    max_steps: Mapped[int]
    max_runtime_seconds: Mapped[int]
    max_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    max_retries: Mapped[int] = mapped_column(server_default="2")
    steps_taken: Mapped[int] = mapped_column(server_default="0")
    retries: Mapped[int] = mapped_column(server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), server_default="0")

    input: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    output: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    steps: Mapped[list[AgentStep]] = relationship(lazy="noload", order_by="AgentStep.position")


class AgentStep(UUIDPk, Base):
    __tablename__ = "agent_steps"
    __table_args__ = (UniqueConstraint("run_id", "position", name="uq_agent_steps_position"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    kind: Mapped[str] = mapped_column(String(24))  # ai_call | tool | decision | result | message
    title: Mapped[str] = mapped_column(String(300))  # "Found 12 relevant topics"
    detail: Mapped[str | None] = mapped_column(Text)  # concise explanation shown on expand
    status: Mapped[AgentRunStatus] = mapped_column(enum_type(AgentRunStatus))
    data: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), server_default="0")
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
