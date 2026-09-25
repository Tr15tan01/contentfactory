from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk, enum_type, jsonb_default
from app.models.enums import MetricScope, Platform


class PlatformMetric(UUIDPk, Base):
    """Latest known metrics for a publication. NULL means the platform does not provide the
    metric — never zero-filled. `available_metrics` lists what the platform reported."""

    __tablename__ = "platform_metrics"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), unique=True
    )
    platform: Mapped[Platform] = mapped_column(enum_type(Platform), index=True)
    impressions: Mapped[int | None] = mapped_column(BigInteger)
    reach: Mapped[int | None] = mapped_column(BigInteger)
    views: Mapped[int | None] = mapped_column(BigInteger)
    likes: Mapped[int | None] = mapped_column(BigInteger)
    comments: Mapped[int | None] = mapped_column(BigInteger)
    shares: Mapped[int | None] = mapped_column(BigInteger)
    saves: Mapped[int | None] = mapped_column(BigInteger)
    clicks: Mapped[int | None] = mapped_column(BigInteger)
    follows: Mapped[int | None] = mapped_column(BigInteger)
    conversions: Mapped[int | None] = mapped_column(BigInteger)
    watch_time_seconds: Mapped[float | None] = mapped_column(Numeric(14, 2))
    avg_watch_seconds: Mapped[float | None] = mapped_column(Numeric(10, 2))
    engagement_rate: Mapped[float | None] = mapped_column(Numeric(8, 5))
    available_metrics: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    raw: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    synced_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


class MetricSnapshot(UUIDPk, Base):
    """Time series: per-publication metric history or account-level (followers) history."""

    __tablename__ = "metric_snapshots"
    __table_args__ = (
        Index("ix_metric_snapshots_pub_time", "publication_id", "captured_at"),
        Index("ix_metric_snapshots_account_time", "social_account_id", "captured_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[MetricScope] = mapped_column(enum_type(MetricScope))
    publication_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE")
    )
    social_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("social_accounts.id", ondelete="CASCADE")
    )
    platform: Mapped[Platform] = mapped_column(enum_type(Platform))
    captured_at: Mapped[datetime] = mapped_column(server_default=func.now())
    metrics: Mapped[dict[str, Any]]
