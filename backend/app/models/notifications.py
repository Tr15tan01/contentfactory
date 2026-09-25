from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, enum_type, jsonb_default
from app.models.enums import NotificationType


class Notification(UUIDPk, Timestamps, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "read_at"),
        Index("ix_notifications_ws_created", "workspace_id", "created_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    # NULL = visible to every member of the workspace.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(enum_type(NotificationType), index=True)
    priority: Mapped[str] = mapped_column(String(8), server_default="normal")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    action_url: Mapped[str | None] = mapped_column(String(500))
    entity_type: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID | None]
    data: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    # Prevents duplicate reminders, e.g. "reminder:24h:<schedule_id>".
    dedupe_key: Mapped[str | None] = mapped_column(String(160), unique=True)
    read_at: Mapped[datetime | None]
    dismissed_at: Mapped[datetime | None]
    emailed_at: Mapped[datetime | None]
    pushed_at: Mapped[datetime | None]


class NotificationPreference(UUIDPk, Timestamps, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", "type", name="uq_notification_preferences_key"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[NotificationType] = mapped_column(enum_type(NotificationType))
    in_app: Mapped[bool] = mapped_column(server_default=text("true"))
    email: Mapped[bool] = mapped_column(server_default=text("false"))
    push: Mapped[bool] = mapped_column(server_default=text("false"))
