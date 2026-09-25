from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import MediaKind, MediaSource, MediaStatus


class UploadIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(max_length=100)
    size_bytes: int = Field(gt=0)
    folder_id: uuid.UUID | None = None


class UploadTargetOut(BaseModel):
    url: str
    method: Literal["POST", "PUT"]
    fields: dict[str, str]
    headers: dict[str, str]


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: MediaKind
    source: MediaSource
    status: MediaStatus
    display_name: str
    original_filename: str | None
    description: str | None
    tags: list[str]
    folder_id: uuid.UUID | None
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    duration_seconds: float | None
    is_favorite: bool
    url: str | None
    thumbnail_url: str | None
    duplicate_of: uuid.UUID | None
    error: str | None
    generator: str | None = None  # image provider for generated files ("mock" = dev placeholder)
    created_at: datetime


class UploadOut(BaseModel):
    asset: MediaOut
    upload: UploadTargetOut


class MediaPageOut(BaseModel):
    items: list[MediaOut]
    next_cursor: str | None
    total: int


class MediaUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=30)
    folder_id: uuid.UUID | None = None
    move_to_unfiled: bool = False
    is_favorite: bool | None = None


class FolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class FolderOut(BaseModel):
    id: uuid.UUID
    name: str
    asset_count: int


class TagCount(BaseModel):
    tag: str
    count: int


class GenerateImageIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)
    aspect: Literal["square", "portrait", "landscape", "story"] = "square"
    use_brand: bool = True
    content_id: uuid.UUID | None = None


class SceneIn(BaseModel):
    media_id: uuid.UUID
    duration_s: float = Field(ge=1, le=30)
    text: str | None = Field(default=None, max_length=120)


class BuildVideoIn(BaseModel):
    scenes: list[SceneIn] = Field(min_length=1, max_length=20)
    aspect: Literal["vertical", "square"] = "vertical"
    title: str | None = Field(default=None, max_length=120)
    content_id: uuid.UUID | None = None


class GeneratedOut(BaseModel):
    asset: MediaOut
    reused: bool
    credits: int = 1
