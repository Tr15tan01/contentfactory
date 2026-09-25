from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.enums import (
    Confidence,
    ContentType,
    ExperimentStatus,
    InsightCategory,
    InsightStatus,
    MemoryCategory,
    MemorySource,
    Platform,
)


class Totals(BaseModel):
    reach: float | None
    views: float | None
    likes: float | None
    comments: float | None
    shares: float | None
    saves: float | None
    engagements: float | None


class PlatformRow(Totals):
    platform: Platform
    posts: int
    measured: int
    unavailable: list[str]


class DayRow(BaseModel):
    date: date
    posts: int
    engagements: float


class TopPost(BaseModel):
    content_id: uuid.UUID
    title: str
    platform: Platform
    content_type: ContentType
    pillar: str | None
    published_at: datetime
    url: str | None
    engagements: float | None
    reach: float | None
    views: float | None
    likes: float | None
    comments: float | None
    shares: float | None
    saves: float | None


class AnalyticsOut(BaseModel):
    days: int
    posts_published: int
    posts_measured: int
    totals: Totals
    platforms: list[PlatformRow]
    daily: list[DayRow]
    top_posts: list[TopPost]


class InsightOut(BaseModel):
    id: uuid.UUID
    category: InsightCategory
    status: InsightStatus
    title: str
    statement: str
    metric: str
    segment_a: str | None
    segment_b: str | None
    value_a: float | None
    value_b: float | None
    relative_change: float | None
    sample_size: int
    period_start: date
    period_end: date
    confidence: Confidence
    evidence: dict[str, Any]
    updated_at: datetime


class MemoryIn(BaseModel):
    content: str = Field(min_length=3, max_length=1000)
    category: MemoryCategory
    pinned: bool = False


class MemoryUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=3, max_length=1000)
    category: MemoryCategory | None = None
    pinned: bool | None = None


class MemoryOut(BaseModel):
    id: uuid.UUID
    category: MemoryCategory
    source: MemorySource
    content: str
    pinned: bool
    evidence: dict[str, Any]
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExperimentIn(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    hypothesis: str = Field(min_length=3, max_length=1000)
    variable: Literal["hook", "cta", "format", "time", "topic", "visual"]
    primary_metric: Literal[
        "engagements", "saves", "reach", "views", "shares", "comments", "likes"
    ] = "engagements"
    variant_a: str = Field(min_length=1, max_length=300)
    variant_b: str = Field(min_length=1, max_length=300)
    min_sample_per_variant: int = Field(default=5, ge=3, le=50)


class AssignIn(BaseModel):
    content_ids: list[uuid.UUID] = Field(max_length=100)


class VariantOut(BaseModel):
    id: uuid.UUID
    label: str
    description: str
    content_ids: list[str]
    sample_size: int
    metrics: dict[str, Any]


class ExperimentOut(BaseModel):
    id: uuid.UUID
    name: str
    hypothesis: str
    variable: str
    primary_metric: str
    status: ExperimentStatus
    min_sample_per_variant: int
    confidence: Confidence
    conclusion: str | None
    result: dict[str, Any]
    winner_variant_id: uuid.UUID | None
    created_at: datetime
    variants: list[VariantOut]
