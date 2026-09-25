"""Provider-neutral social publishing interface.

Adapters talk to each platform's official API. Nothing here ever reports success unless the
platform returned an id for the post.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

import httpx

from app.models.enums import ContentType, Platform


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    refresh_expires_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)


@dataclass
class RemoteAccount:
    platform: Platform
    external_id: str
    display_name: str | None
    username: str | None
    avatar_url: str | None
    token: TokenSet
    capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass
class MediaItem:
    kind: str  # "image" | "video"
    url: str  # absolute URL the platform can fetch
    mime_type: str
    size_bytes: int
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    open: Callable[[], AsyncIterator[bytes]] | None = None  # byte stream, for push uploads


@dataclass
class PublishRequest:
    platform: Platform
    content_type: ContentType
    title: str
    caption: str
    media: list[MediaItem]


@dataclass
class PublishResult:
    post_id: str
    url: str | None
    details: dict[str, Any] = field(default_factory=dict)


class SocialError(Exception):
    """`retryable`: try again later. `needs_reauth`: the connection must be renewed.
    `processing`: the platform accepted the upload and is still processing it."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        retryable: bool = False,
        needs_reauth: bool = False,
        processing: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable or processing
        self.needs_reauth = needs_reauth
        self.processing = processing


class SocialAdapter(Protocol):
    provider: str
    platforms: tuple[Platform, ...]
    label: str

    def configured(self) -> bool: ...

    def authorize_url(self, state: str, verifier: str, redirect_uri: str) -> str: ...

    async def connect(self, code: str, verifier: str, redirect_uri: str) -> list[RemoteAccount]: ...

    async def refresh(self, token: TokenSet) -> TokenSet | None: ...

    def validate(self, req: PublishRequest) -> list[str]: ...

    async def publish(
        self, account_id: str, token: TokenSet, req: PublishRequest, state: dict[str, Any]
    ) -> PublishResult: ...

    async def fetch_metrics(
        self,
        platform: Platform,
        account_id: str,
        token: TokenSet,
        post_id: str,
        content_type: ContentType,
    ) -> dict[str, float]:
        """Only metrics the platform reported. A missing key means "not available", never 0."""
        ...


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


def challenge_for(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )


def http_error(r: httpx.Response, fallback: str) -> SocialError:
    """Generic mapping: 401 -> reconnect, 429/5xx -> retry later, others -> permanent."""
    if r.status_code == 401:
        return SocialError(
            "The connection was rejected. Reconnect the account.", code="auth", needs_reauth=True
        )
    if r.status_code == 429 or r.status_code >= 500:
        return SocialError(
            f"{fallback} is busy or rate-limited. Retrying.", code="unavailable", retryable=True
        )
    return SocialError(f"{fallback} rejected the request ({r.status_code}).", code="rejected")


def media_problems(req: PublishRequest, *, need_video: bool, max_images: int = 1) -> list[str]:
    videos = [m for m in req.media if m.kind == "video"]
    images = [m for m in req.media if m.kind == "image"]
    problems = []
    if need_video and not videos:
        problems.append("This format needs a video.")
    if not need_video and not req.media and req.content_type.value != "post":
        problems.append("Attach a photo or video.")
    if len(images) > max_images:
        problems.append(f"Up to {max_images} images are supported here.")
    return problems
