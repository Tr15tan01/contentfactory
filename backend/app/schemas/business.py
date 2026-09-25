from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator

from app.models.enums import Platform

Short = Annotated[str, Field(min_length=1, max_length=200)]
ShortList = Annotated[list[Short], Field(max_length=20)]


def _clean_list(values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        v = " ".join(v.split())
        if v and v.lower() not in {o.lower() for o in out}:
            out.append(v)
    return out


CleanList = Annotated[ShortList, AfterValidator(_clean_list)]

Goal = Literal[
    "more_visits",
    "more_bookings",
    "online_sales",
    "leads",
    "awareness",
    "followers",
    "loyalty",
    "launch",
]


def _url(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    value = value.strip()
    if not re.match(r"^https?://", value, re.I):
        value = f"https://{value}"
    if not re.match(r"^https?://[^\s/$.?#][^\s]*\.[^\s]{2,}", value, re.I):
        raise ValueError("Enter a website address like example.com.")
    return value[:500]


class Audience(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    customer_types: CleanList = []
    pain_points: CleanList = []


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    industry: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=200)
    website: Annotated[str | None, AfterValidator(_url)] = None
    preferred_language: str = Field(default="en", min_length=2, max_length=16)
    audience: Audience = Audience()
    unique_selling_points: CleanList = []
    competitors: CleanList = []
    marketing_goals: Annotated[list[Goal], Field(max_length=8)] = []
    topics_to_avoid: CleanList = []

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Enter your business name.")
        return " ".join(v.split())

    @field_validator("industry", "location", "description")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v is not None else None


class ProfileOut(ProfileIn):
    name: str


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _colors(values: list[str]) -> list[str]:
    for v in values:
        if not _HEX.match(v):
            raise ValueError("Colours must be hex values like #0E6B63.")
    return [v.upper() for v in values]


class BrandIn(BaseModel):
    voice: str | None = Field(default=None, max_length=2000)
    tone: Annotated[list[Annotated[str, Field(max_length=40)]], Field(max_length=8)] = []
    colors: Annotated[list[str], Field(max_length=8), AfterValidator(_colors)] = []
    visual_style: str | None = Field(default=None, max_length=2000)
    words_to_use: CleanList = []
    words_to_avoid: CleanList = []
    logo_asset_id: uuid.UUID | None = None


class BrandOut(BrandIn):
    logo_url: str | None = None


class PreferencesIn(BaseModel):
    prefer_media: Literal["always", "when_relevant", "never"] = "when_relevant"
    approval_required: bool = True
    reminder_offsets_hours: Annotated[list[Literal[24, 6, 1]], Field(max_length=3)] = [24]
    posts_per_week: int = Field(default=3, ge=1, le=21)
    preferred_platforms: Annotated[list[Platform], Field(max_length=7)] = []


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    price: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"), decimal_places=2)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    benefits: CleanList = []
    target_customer: str | None = Field(default=None, max_length=2000)
    url: Annotated[str | None, AfterValidator(_url)] = None
    media_ids: Annotated[list[uuid.UUID], Field(max_length=10)] = []


class ProductOut(ProductIn):
    id: uuid.UUID
    position: int
    thumbnails: list[str] = []


class OnboardingIn(BaseModel):
    step: int = Field(ge=1, le=7)
    complete: bool = False


class OnboardingOut(BaseModel):
    step: int
    completed: bool


class BusinessOut(BaseModel):
    profile: ProfileOut | None
    brand: BrandOut
    preferences: PreferencesIn
    products: list[ProductOut]
    onboarding: OnboardingOut
    plan: str
    can_auto_publish: bool
