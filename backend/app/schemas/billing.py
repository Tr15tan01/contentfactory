from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import Plan


class ScheduledChange(BaseModel):
    action: str | None
    effective_at: str | None


class BillingOut(BaseModel):
    configured: bool
    environment: str
    client_token: str | None
    plan: str
    billed_plan: str
    manual_override: str | None
    status: str
    has_paddle_subscription: bool
    current_period_start: datetime | None
    current_period_end: datetime | None
    scheduled_change: ScheduledChange | None
    price_cents: int | None
    currency: str | None
    last_webhook_at: datetime | None


class PlanIn(BaseModel):
    plan: Plan


class CheckoutOut(BaseModel):
    price_id: str
    client_token: str
    environment: str
    customer_email: str
    custom_data: dict[str, Any]


class PendingOut(BaseModel):
    status: str
    direction: str | None = None


class PortalOut(BaseModel):
    url: str
