from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import Platform, SocialAccountStatus


class ProviderOut(BaseModel):
    provider: str
    label: str
    platforms: list[Platform]
    configured: bool
    connected: int


class AccountOut(BaseModel):
    id: uuid.UUID
    platform: Platform
    status: SocialAccountStatus
    display_name: str | None
    username: str | None
    avatar_url: str | None
    last_error: str | None
    token_expires_at: datetime | None
    connected_at: datetime
    capabilities: dict[str, Any]


class Limit(BaseModel):
    used: int
    limit: int


class SocialOut(BaseModel):
    providers: list[ProviderOut]
    accounts: list[AccountOut]
    limit: Limit
    publishing_needs_public_media: bool


class ConnectOut(BaseModel):
    authorize_url: str
