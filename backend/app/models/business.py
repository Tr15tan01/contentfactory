from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDelete, Timestamps, UUIDPk, jsonb_default


class BusinessProfile(UUIDPk, Timestamps, Base):
    """What the business owner tells us once. Seeds the Business Marketing Memory."""

    __tablename__ = "business_profiles"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True
    )
    name: Mapped[str] = mapped_column(String(120))
    industry: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))
    website: Mapped[str | None] = mapped_column(String(500))
    preferred_language: Mapped[str] = mapped_column(String(16), server_default="en")
    content_style: Mapped[str | None] = mapped_column(String(200))
    posting_frequency: Mapped[str | None] = mapped_column(String(64))
    # {"description", "age_range", "locations", "interests", "problems", "buying_intent"}
    audience: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
    unique_selling_points: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    competitors: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    marketing_goals: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    preferred_platforms: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    topics_to_avoid: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    onboarding_step: Mapped[int] = mapped_column(server_default="1")
    onboarding_completed_at: Mapped[datetime | None]


class Brand(UUIDPk, Timestamps, Base):
    __tablename__ = "brands"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True
    )
    voice: Mapped[str | None] = mapped_column(Text)
    tone: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    colors: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    fonts: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    visual_style: Mapped[str | None] = mapped_column(Text)
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    guidelines: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())


class Product(UUIDPk, Timestamps, SoftDelete, Base):
    __tablename__ = "products"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), server_default="USD")
    benefits: Mapped[list[Any]] = mapped_column(server_default=jsonb_default("[]"))
    target_customer: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000))
    position: Mapped[int] = mapped_column(server_default="0")


class ProductMedia(UUIDPk, Base):
    __tablename__ = "product_media"
    __table_args__ = (
        UniqueConstraint("product_id", "media_asset_id", name="uq_product_media_pair"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(server_default="0")
