from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, enum_type, jsonb_default
from app.models.enums import Plan, SubscriptionStatus


class Subscription(UUIDPk, Timestamps, Base):
    """Billing state for an account (the paying user). Workspaces owned by that user inherit
    its entitlements. Only Paddle webhooks (or an audited admin override) change this row."""

    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    plan: Mapped[Plan] = mapped_column(enum_type(Plan), index=True)
    status: Mapped[SubscriptionStatus] = mapped_column(enum_type(SubscriptionStatus), index=True)
    paddle_customer_id: Mapped[str | None] = mapped_column(String(64), index=True)
    paddle_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    paddle_product_id: Mapped[str | None] = mapped_column(String(64))
    paddle_price_id: Mapped[str | None] = mapped_column(String(64))
    billing_interval: Mapped[str | None] = mapped_column(String(16))
    unit_price_cents: Mapped[int | None]
    currency: Mapped[str | None] = mapped_column(String(3))
    current_period_start: Mapped[datetime | None]
    current_period_end: Mapped[datetime | None]
    # Paddle's scheduled_change: {"action": "cancel"|"pause"|"resume", "effective_at": ...}
    scheduled_change: Mapped[dict[str, Any] | None]
    canceled_at: Mapped[datetime | None]
    last_webhook_at: Mapped[datetime | None]
    # Paddle event occurred_at of the last applied event — older events are ignored.
    last_event_occurred_at: Mapped[datetime | None]
    manual_plan_override: Mapped[Plan | None] = mapped_column(enum_type(Plan, "manual_plan"))
    quota_reset_at: Mapped[datetime | None]


class BillingEvent(UUIDPk, Base):
    """Every Paddle webhook, stored once (unique event id) before processing."""

    __tablename__ = "billing_events"

    paddle_event_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime]
    received_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    processed_at: Mapped[datetime | None]
    processing_error: Mapped[str | None] = mapped_column(Text)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"), index=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(server_default=jsonb_default())
