from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDelete, Timestamps, UUIDPk, enum_type, jsonb_default
from app.models.enums import Platform, SocialAccountStatus


class SocialAccount(UUIDPk, Timestamps, SoftDelete, Base):
    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "platform", "external_account_id", name="uq_social_accounts_external"
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[Platform] = mapped_column(enum_type(Platform), index=True)
    status: Mapped[SocialAccountStatus] = mapped_column(enum_type(SocialAccountStatus), index=True)
    external_account_id: Mapped[str] = mapped_column(String(128))
    display_name: Mapped[str | None] = mapped_column(String(200))
    username: Mapped[str | None] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    scopes: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    # What this connection can actually do right now (from the adapter + granted scopes).
    capabilities: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    connected_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    last_synced_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(1000))


class SocialAccountToken(UUIDPk, Timestamps, Base):
    """Encrypted OAuth credentials. Only workers decrypt these; the API never returns them."""

    __tablename__ = "social_account_tokens"

    social_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE"), unique=True
    )
    access_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    refresh_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_type: Mapped[str | None] = mapped_column(String(32))
    expires_at: Mapped[datetime | None]
    refresh_expires_at: Mapped[datetime | None]
