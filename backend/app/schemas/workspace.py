from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import WorkspaceRole
from app.schemas.validators import iana_timezone


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: WorkspaceRole
    timezone: str
    is_demo: bool
    onboarding_completed: bool
    settings: dict[str, Any]


class WorkspaceUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = Field(default=None, max_length=64)

    _tz = field_validator("timezone")(iana_timezone)


class WeekStats(BaseModel):
    period_start: datetime
    period_end: datetime
    created: int
    published: int
    scheduled: int
    awaiting_approval: int


class PerformanceSummary(BaseModel):
    period_days: int
    posts_measured: int
    reach: int | None
    views: int | None
    engagements: int | None


class UpcomingItem(BaseModel):
    content_id: uuid.UUID
    title: str
    platform: str
    content_type: str
    status: str
    scheduled_at: datetime


class AttentionItem(BaseModel):
    kind: Literal[
        "finish_onboarding",
        "approve_content",
        "connect_account",
        "renew_connection",
        "publication_failed",
        "approval_overdue",
    ]
    title: str
    description: str
    action_url: str
    priority: Literal["high", "normal"]


class AgentActivity(BaseModel):
    run_id: uuid.UUID
    agent: str
    status: str
    goal: str
    latest_step: str | None
    updated_at: datetime


class LearnedInsight(BaseModel):
    id: uuid.UUID
    statement: str
    sample_size: int
    period_start: date
    period_end: date
    platform: str | None
    confidence: str


class DashboardOut(BaseModel):
    business_name: str
    is_demo: bool
    week: WeekStats
    performance: PerformanceSummary
    upcoming: list[UpcomingItem]
    attention: list[AttentionItem]
    agent: list[AgentActivity]
    learned: list[LearnedInsight]
