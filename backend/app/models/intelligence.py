from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDelete, Timestamps, UUIDPk, enum_type, jsonb_default
from app.models.enums import (
    Confidence,
    ExperimentStatus,
    InsightCategory,
    InsightStatus,
    MemoryCategory,
    MemorySource,
    Platform,
)

EMBEDDING_DIMENSIONS = 1536  # must match AI_EMBEDDING_DIMENSIONS; changing it needs a migration


class MarketingInsight(UUIDPk, Timestamps, Base):
    """A statement computed from real data. Every insight carries its evidence window and
    sample size; the UI refuses to show conclusions below the minimum sample."""

    __tablename__ = "marketing_insights"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[InsightCategory] = mapped_column(enum_type(InsightCategory), index=True)
    status: Mapped[InsightStatus] = mapped_column(enum_type(InsightStatus), index=True)
    title: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(String(32))
    segment_a: Mapped[str | None] = mapped_column(String(120))
    segment_b: Mapped[str | None] = mapped_column(String(120))
    value_a: Mapped[float | None] = mapped_column(Numeric(14, 4))
    value_b: Mapped[float | None] = mapped_column(Numeric(14, 4))
    relative_change: Mapped[float | None] = mapped_column(Numeric(10, 4))
    sample_size: Mapped[int]
    period_start: Mapped[date]
    period_end: Mapped[date]
    platform: Mapped[Platform | None] = mapped_column(enum_type(Platform))
    confidence: Mapped[Confidence] = mapped_column(enum_type(Confidence))
    evidence: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    # Stable identity of the comparison (e.g. "pillar:saves:all"), so re-analysis updates an
    # insight instead of piling up duplicates.
    key: Mapped[str | None] = mapped_column(String(120), index=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL")
    )


class MarketingMemory(UUIDPk, Timestamps, SoftDelete, Base):
    """Business-specific knowledge the agents retrieve (by category + vector similarity)
    before they write. This is how the product 'learns' without retraining a model."""

    __tablename__ = "marketing_memory"
    __table_args__ = (
        Index("ix_marketing_memory_ws_category", "workspace_id", "category"),
        Index(
            "ix_marketing_memory_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[MemoryCategory] = mapped_column(enum_type(MemoryCategory))
    source: Mapped[MemorySource] = mapped_column(enum_type(MemorySource))
    content: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, server_default="1.0")
    evidence: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    last_used_at: Mapped[datetime | None]
    # Pinned memories are always included in AI context, whatever the query.
    pinned: Mapped[bool] = mapped_column(server_default=text("false"))
    expires_at: Mapped[datetime | None]


class Experiment(UUIDPk, Timestamps, Base):
    __tablename__ = "experiments"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    hypothesis: Mapped[str] = mapped_column(Text)
    variable: Mapped[str] = mapped_column(String(32))  # hook | cta | format | time | topic
    primary_metric: Mapped[str] = mapped_column(String(32))
    status: Mapped[ExperimentStatus] = mapped_column(enum_type(ExperimentStatus), index=True)
    platform: Mapped[Platform | None] = mapped_column(enum_type(Platform))
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]
    min_sample_per_variant: Mapped[int] = mapped_column(server_default="5")
    winner_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiment_variants.id", ondelete="SET NULL", use_alter=True)
    )
    confidence: Mapped[Confidence] = mapped_column(enum_type(Confidence))
    result: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    conclusion: Mapped[str | None] = mapped_column(Text)

    variants: Mapped[list[ExperimentVariant]] = relationship(
        lazy="noload", foreign_keys="ExperimentVariant.experiment_id"
    )


class ExperimentVariant(UUIDPk, Timestamps, Base):
    __tablename__ = "experiment_variants"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(8))
    description: Mapped[str] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    sample_size: Mapped[int] = mapped_column(server_default="0")
    metrics: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())


class ResearchItem(UUIDPk, Timestamps, Base):
    """Cached research. External content is untrusted: it's stored as data and passed to
    models inside clearly delimited, instruction-stripped blocks."""

    __tablename__ = "research_items"
    __table_args__ = (Index("ix_research_items_ws_query", "workspace_id", "query_fingerprint"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    query_fingerprint: Mapped[str] = mapped_column(String(64))
    topic: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(String(2000))
    title: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    relevance: Mapped[float | None] = mapped_column(Float)
    trusted: Mapped[bool] = mapped_column(server_default=text("false"))
    data: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    expires_at: Mapped[datetime | None] = mapped_column(index=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
