from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDelete, Timestamps, UUIDPk, enum_type, jsonb_default
from app.models.enums import (
    ContentOrigin,
    ContentStatus,
    ContentType,
    Platform,
    PublicationStatus,
    ScheduleStatus,
)


class Content(UUIDPk, Timestamps, SoftDelete, Base):
    """A piece of marketing content. Platform-specific copy lives in ContentVariant."""

    __tablename__ = "contents"
    __table_args__ = (Index("ix_contents_workspace_status", "workspace_id", "status"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL")
    )
    experiment_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiment_variants.id", ondelete="SET NULL"), index=True
    )

    status: Mapped[ContentStatus] = mapped_column(enum_type(ContentStatus), index=True)
    content_type: Mapped[ContentType] = mapped_column(enum_type(ContentType))
    origin: Mapped[ContentOrigin] = mapped_column(enum_type(ContentOrigin))

    title: Mapped[str] = mapped_column(String(200))
    topic: Mapped[str | None] = mapped_column(String(300))
    pillar: Mapped[str | None] = mapped_column(String(120))
    goal: Mapped[str | None] = mapped_column(String(64))
    tone: Mapped[str | None] = mapped_column(String(64))
    hook: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(String(300))
    caption: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    cta: Mapped[str | None] = mapped_column(String(300))
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String(100)), server_default=text("'{}'"))
    visual_concept: Mapped[str | None] = mapped_column(Text)
    image_prompt: Mapped[str | None] = mapped_column(Text)
    # {"scenes": [...], "voiceover": ..., "subtitles": ...}
    video_script: Mapped[dict[str, Any] | None]
    # Tags the analytics agent groups by: format, hook_style, cta_style, topic_cluster, ...
    attributes: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())

    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None]
    rejected_reason: Mapped[str | None] = mapped_column(Text)

    variants: Mapped[list[ContentVariant]] = relationship(lazy="noload", back_populates="content")


class ContentVariant(UUIDPk, Timestamps, Base):
    __tablename__ = "content_variants"
    __table_args__ = (
        UniqueConstraint("content_id", "platform", name="uq_content_variants_platform"),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[Platform] = mapped_column(enum_type(Platform), index=True)
    caption: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(ARRAY(String(100)), server_default=text("'{}'"))
    cta: Mapped[str | None] = mapped_column(String(300))
    options: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())

    content: Mapped[Content] = relationship(lazy="noload", back_populates="variants")


class ContentMedia(UUIDPk, Base):
    __tablename__ = "content_media"
    __table_args__ = (
        UniqueConstraint("content_id", "media_asset_id", name="uq_content_media_pair"),
    )

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[str] = mapped_column(String(24), server_default="primary")
    position: Mapped[int] = mapped_column(server_default="0")


class ContentSchedule(UUIDPk, Timestamps, Base):
    __tablename__ = "content_schedules"
    __table_args__ = (Index("ix_content_schedules_workspace_time", "workspace_id", "scheduled_at"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    social_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="SET NULL")
    )
    platform: Mapped[Platform] = mapped_column(enum_type(Platform), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(index=True)
    status: Mapped[ScheduleStatus] = mapped_column(enum_type(ScheduleStatus), index=True)
    reminders_sent: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))


class Publication(UUIDPk, Timestamps, Base):
    """One attempt-set to put a content variant on a platform. Idempotency key guarantees
    that a retried worker never publishes twice."""

    __tablename__ = "publications"
    __table_args__ = (
        Index("ix_publications_platform_post", "platform", "platform_post_id"),
        Index("ix_publications_status_retry", "status", "next_retry_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    content_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_variants.id", ondelete="SET NULL")
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_schedules.id", ondelete="SET NULL")
    )
    social_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="SET NULL"), index=True
    )
    platform: Mapped[Platform] = mapped_column(enum_type(Platform), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[PublicationStatus] = mapped_column(enum_type(PublicationStatus), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(index=True)
    published_at: Mapped[datetime | None] = mapped_column(index=True)
    platform_post_id: Mapped[str | None] = mapped_column(String(200))
    platform_url: Mapped[str | None] = mapped_column(String(1024))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(server_default="0")
    next_retry_at: Mapped[datetime | None]
    last_attempt_at: Mapped[datetime | None]
    # Provider progress kept between attempts (e.g. an Instagram container id or a TikTok
    # publish id), so a retry resumes the same upload instead of starting a duplicate.
    provider_state: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())


class ContentVersion(UUIDPk, Base):
    """Snapshot of a post before each change (edit, regenerate, approval reset)."""

    __tablename__ = "content_versions"
    __table_args__ = (UniqueConstraint("content_id", "version", name="uq_content_version"),)

    content_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int]
    reason: Mapped[str] = mapped_column(String(32))
    snapshot: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
