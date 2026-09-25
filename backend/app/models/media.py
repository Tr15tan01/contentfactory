from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDelete, Timestamps, UUIDPk, enum_type, jsonb_default
from app.models.enums import MediaKind, MediaSource, MediaStatus


class MediaFolder(UUIDPk, Timestamps, SoftDelete, Base):
    __tablename__ = "media_folders"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_folders.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120))


class MediaAsset(UUIDPk, Timestamps, SoftDelete, Base):
    """Metadata for a file in object storage. Bytes never live in PostgreSQL."""

    __tablename__ = "media_assets"
    __table_args__ = (
        Index("ix_media_assets_workspace_checksum", "workspace_id", "checksum_sha256"),
        Index("ix_media_assets_workspace_prompt", "workspace_id", "generation_fingerprint"),
        Index("ix_media_assets_tags", "tags", postgresql_using="gin"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_folders.id", ondelete="SET NULL"), index=True
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    kind: Mapped[MediaKind] = mapped_column(enum_type(MediaKind))
    source: Mapped[MediaSource] = mapped_column(enum_type(MediaSource))
    status: Mapped[MediaStatus] = mapped_column(enum_type(MediaStatus), index=True)

    storage_bucket: Mapped[str] = mapped_column(String(120))
    storage_key: Mapped[str] = mapped_column(String(700), unique=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(700))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None]
    height: Mapped[int | None]
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(10, 3))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    # Hash of (model, normalized prompt, params) for generated media: never pay twice.
    generation_fingerprint: Mapped[str | None] = mapped_column(String(64))

    original_filename: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    alt_text: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), server_default=text("'{}'"))
    is_favorite: Mapped[bool] = mapped_column(server_default=text("false"))
    # Vision-model description, detected objects, dominant colours — used for asset selection.
    ai_metadata: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
