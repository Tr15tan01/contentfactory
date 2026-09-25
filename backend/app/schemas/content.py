from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, Field

from app.models.enums import ContentOrigin, ContentStatus, ContentType, Platform

Platforms = Annotated[list[Platform], Field(min_length=1, max_length=4)]
MediaIds = Annotated[list[uuid.UUID], Field(max_length=10)]


class GenerateIn(BaseModel):
    idea: str | None = Field(default=None, max_length=1000)
    platforms: Platforms
    content_type: ContentType = ContentType.POST
    goal: str | None = Field(default=None, max_length=64)
    product_id: uuid.UUID | None = None
    media_ids: MediaIds = []
    scheduled_at: AwareDatetime | None = None


class VariantIn(BaseModel):
    platform: Platform
    caption: str = Field(default="", max_length=10000)
    hashtags: Annotated[list[Annotated[str, Field(max_length=100)]], Field(max_length=40)] = []
    cta: str | None = Field(default=None, max_length=300)


class CreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content_type: ContentType = ContentType.POST
    platforms: Platforms
    hook: str | None = Field(default=None, max_length=1000)
    caption: str = Field(default="", max_length=10000)
    hashtags: Annotated[list[str], Field(max_length=40)] = []
    cta: str | None = Field(default=None, max_length=300)
    media_ids: MediaIds = []
    product_id: uuid.UUID | None = None


class UpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    hook: str | None = Field(default=None, max_length=1000)
    visual_concept: str | None = Field(default=None, max_length=2000)
    variants: Annotated[list[VariantIn], Field(min_length=1, max_length=4)] | None = None
    media_ids: MediaIds | None = None
    script: list[dict[str, Any]] | None = None
    slides: list[dict[str, Any]] | None = None


class RegenerateIn(BaseModel):
    instruction: str | None = Field(default=None, max_length=500)


class RejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ScheduleIn(BaseModel):
    scheduled_at: AwareDatetime


class VariantOut(BaseModel):
    platform: Platform
    caption: str
    hashtags: list[str]
    cta: str | None


class ContentMediaOut(BaseModel):
    id: uuid.UUID
    kind: str
    display_name: str
    thumbnail_url: str | None
    url: str | None


class ScheduleOut(BaseModel):
    scheduled_at: datetime
    platforms: list[Platform]
    status: str


class Warning(BaseModel):
    code: str
    message: str


class GenerationInfo(BaseModel):
    provider: str | None
    model: str | None
    cached: bool
    error: str | None


class PublicationOut(BaseModel):
    id: uuid.UUID
    platform: Platform
    status: str
    scheduled_at: datetime
    published_at: datetime | None
    platform_url: str | None
    error_code: str | None
    error_message: str | None
    retry_count: int
    next_retry_at: datetime | None


class ContentOut(BaseModel):
    id: uuid.UUID
    status: ContentStatus
    content_type: ContentType
    origin: ContentOrigin
    title: str
    topic: str | None
    pillar: str | None
    goal: str | None
    hook: str | None
    visual_concept: str | None
    image_prompt: str | None
    script: list[dict[str, Any]] | None
    slides: list[dict[str, Any]] | None
    variants: list[VariantOut]
    media: list[ContentMediaOut]
    product_id: uuid.UUID | None
    schedule: ScheduleOut | None
    approved_at: datetime | None
    rejected_reason: str | None
    warnings: list[Warning]
    publications: list[PublicationOut] = []
    missing_accounts: list[Platform] = []
    generation: GenerationInfo
    version: int
    created_at: datetime
    updated_at: datetime


class ContentListItem(BaseModel):
    id: uuid.UUID
    title: str
    status: ContentStatus
    content_type: ContentType
    pillar: str | None
    platforms: list[Platform]
    scheduled_at: datetime | None
    thumbnail_url: str | None
    warnings: int
    updated_at: datetime


class ContentPage(BaseModel):
    items: list[ContentListItem]
    total: int


class VersionOut(BaseModel):
    version: int
    reason: str
    created_at: datetime
    created_by: str | None
    title: str
    hook: str | None


class UsageBucket(BaseModel):
    used: int
    limit: int
    remaining: int


class UsageOut(BaseModel):
    plan: str
    period_start: datetime
    period_end: datetime
    ai_content: UsageBucket
    images: UsageBucket
    video_credits: UsageBucket
    scheduled_posts: UsageBucket
    ai_provider: str
    image_provider: str
    video_builder: bool
