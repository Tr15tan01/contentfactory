from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDelete, Timestamps, UUIDPk, enum_type, jsonb_default
from app.models.enums import WorkspaceRole


class Workspace(UUIDPk, Timestamps, SoftDelete, Base):
    """A business (or an agency client). Every business-scoped row carries workspace_id."""

    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    timezone: Mapped[str] = mapped_column(String(64), server_default="UTC")
    # Demo workspaces are created by the seed script and are never billed or published.
    is_demo: Mapped[bool] = mapped_column(server_default=text("false"))
    # Agent + approval settings: prefer_media, autopilot, reminder offsets, limits.
    settings: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())

    members: Mapped[list[WorkspaceMember]] = relationship(back_populates="workspace", lazy="noload")


class WorkspaceMember(UUIDPk, Timestamps, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_pair"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[WorkspaceRole] = mapped_column(enum_type(WorkspaceRole))

    workspace: Mapped[Workspace] = relationship(back_populates="members", lazy="noload")
