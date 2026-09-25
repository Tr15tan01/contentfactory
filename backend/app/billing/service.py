"""Billing. Paddle webhooks are the only thing that changes a paid plan.

Checkout and plan changes start in Paddle; the resulting subscription events arrive as signed
webhooks, are stored once (idempotent on event id), ignored if older than what we already
applied (Paddle doesn't guarantee order), and only then change the subscription row.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import paddle
from app.billing.entitlements import apply_plan_constraints, effective_plan, user_subscription
from app.core.config import settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.models import BillingEvent, Subscription, User
from app.models.enums import Plan, SubscriptionStatus
from app.services import audit

log = logging.getLogger("contentfactory.billing")
ORDER = [Plan.FREE, Plan.STARTER, Plan.BUSINESS, Plan.AGENCY]
STATUS_MAP = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.TRIALING,
    "past_due": SubscriptionStatus.PAST_DUE,
    "paused": SubscriptionStatus.PAUSED,
    "canceled": SubscriptionStatus.CANCELED,
}


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _has_paid_subscription(sub: Subscription | None) -> bool:
    return bool(
        sub and sub.paddle_subscription_id and sub.status is not SubscriptionStatus.CANCELED
    )


async def _subscription(db: AsyncSession, user: User) -> Subscription:
    sub = await user_subscription(db, user.id)
    if sub is None:  # accounts created before provisioning existed
        sub = Subscription(user_id=user.id, plan=Plan.FREE, status=SubscriptionStatus.ACTIVE)
        db.add(sub)
        await db.flush()
    return sub


async def overview(db: AsyncSession, user: User) -> dict[str, Any]:
    sub = await _subscription(db, user)
    plan = effective_plan(sub)
    change = sub.scheduled_change or None
    return {
        "configured": paddle.configured(),
        "environment": settings.PADDLE_ENVIRONMENT,
        "client_token": settings.PADDLE_CLIENT_TOKEN if paddle.configured() else None,
        "plan": plan.value,
        "billed_plan": sub.plan.value,
        "manual_override": sub.manual_plan_override.value if sub.manual_plan_override else None,
        "status": sub.status.value,
        "has_paddle_subscription": _has_paid_subscription(sub),
        "current_period_start": sub.current_period_start,
        "current_period_end": sub.current_period_end,
        "scheduled_change": (
            {"action": change.get("action"), "effective_at": change.get("effective_at")}
            if change
            else None
        ),
        "price_cents": sub.unit_price_cents,
        "currency": sub.currency,
        "last_webhook_at": sub.last_webhook_at,
    }


def _require_configured() -> None:
    if not paddle.configured():
        raise AppError(
            503,
            "billing_unavailable",
            "Paid plans aren't available on this server yet. Billing isn't configured.",
        )


async def checkout(db: AsyncSession, user: User, plan: Plan) -> dict[str, Any]:
    _require_configured()
    if plan is Plan.FREE:
        raise AppError(422, "invalid_plan", "Choose a paid plan.")
    sub = await _subscription(db, user)
    if _has_paid_subscription(sub):
        raise AppError(
            409, "already_subscribed", "You already have a subscription. Change your plan instead."
        )
    return {
        "price_id": paddle.price_for_plan(plan),
        "client_token": settings.PADDLE_CLIENT_TOKEN,
        "environment": settings.PADDLE_ENVIRONMENT,
        "customer_email": user.email,
        "custom_data": {"user_id": str(user.id), "sig": paddle.sign_custom_data(str(user.id))},
    }


async def change_plan(
    db: AsyncSession, client: paddle.PaddleClient, user: User, plan: Plan
) -> dict[str, Any]:
    _require_configured()
    sub = await _subscription(db, user)
    if not _has_paid_subscription(sub):
        raise AppError(409, "no_subscription", "Start a subscription from the plans below first.")
    if plan is Plan.FREE:
        raise AppError(
            422,
            "use_cancel",
            "To move to Free, cancel your subscription. It stays active until the period ends.",
        )
    if plan is sub.plan and not sub.scheduled_change:
        raise AppError(409, "same_plan", "You're already on this plan.")
    assert sub.paddle_subscription_id
    try:
        await client.change_price(sub.paddle_subscription_id, paddle.price_for_plan(plan))
    except paddle.PaddleError as exc:
        raise AppError(502, "billing_provider_error", str(exc)) from exc
    audit.record(
        db,
        "billing.plan_change_requested",
        actor_user_id=user.id,
        data={"to": plan.value, "from": sub.plan.value},
    )
    await db.commit()
    direction = "upgrade" if ORDER.index(plan) > ORDER.index(sub.plan) else "downgrade"
    return {"status": "pending", "direction": direction}


async def cancel(db: AsyncSession, client: paddle.PaddleClient, user: User) -> dict[str, Any]:
    _require_configured()
    sub = await _subscription(db, user)
    if not _has_paid_subscription(sub):
        raise AppError(409, "no_subscription", "There's no paid subscription to cancel.")
    assert sub.paddle_subscription_id
    try:
        await client.cancel(sub.paddle_subscription_id)
    except paddle.PaddleError as exc:
        raise AppError(502, "billing_provider_error", str(exc)) from exc
    audit.record(db, "billing.cancel_requested", actor_user_id=user.id)
    await db.commit()
    return {"status": "pending"}


async def resume(db: AsyncSession, client: paddle.PaddleClient, user: User) -> dict[str, Any]:
    _require_configured()
    sub = await _subscription(db, user)
    if not (_has_paid_subscription(sub) and sub.scheduled_change):
        raise AppError(409, "nothing_to_resume", "There's no scheduled cancellation to undo.")
    assert sub.paddle_subscription_id
    try:
        await client.remove_scheduled_change(sub.paddle_subscription_id)
    except paddle.PaddleError as exc:
        raise AppError(502, "billing_provider_error", str(exc)) from exc
    audit.record(db, "billing.resume_requested", actor_user_id=user.id)
    await db.commit()
    return {"status": "pending"}


async def portal(db: AsyncSession, client: paddle.PaddleClient, user: User) -> str:
    _require_configured()
    sub = await _subscription(db, user)
    if not sub.paddle_customer_id:
        raise AppError(
            409, "no_customer", "Invoices and payment methods appear after your first payment."
        )
    try:
        url = await client.portal_url(sub.paddle_customer_id, sub.paddle_subscription_id)
    except paddle.PaddleError as exc:
        raise AppError(502, "billing_provider_error", str(exc)) from exc
    if not url:
        raise AppError(502, "billing_provider_error", "Paddle didn't return a portal link.")
    return url


# ----------------------------------------------------------------------------- webhooks
async def record_event(db: AsyncSession, payload: dict[str, Any]) -> BillingEvent | None:
    """Store the event once. Returns None for a duplicate delivery."""
    event_id = str(payload.get("event_id") or "")
    if not event_id:
        raise AppError(400, "invalid_event", "Missing event_id.")
    stmt = (
        insert(BillingEvent)
        .values(
            paddle_event_id=event_id,
            event_type=str(payload.get("event_type") or "unknown")[:64],
            occurred_at=_ts(payload.get("occurred_at")) or utcnow(),
            payload=payload,
        )
        .on_conflict_do_nothing(index_elements=["paddle_event_id"])
        .returning(BillingEvent.id)
    )
    new_id = (await db.execute(stmt)).scalar_one_or_none()
    if new_id is None:
        return None
    return await db.get(BillingEvent, new_id)


async def _find_subscription(db: AsyncSession, data: dict[str, Any]) -> Subscription | None:
    sid = (
        data.get("id")
        if str(data.get("id", "")).startswith("sub_")
        else data.get("subscription_id")
    )
    if sid:
        found = (
            await db.execute(
                select(Subscription)
                .where(Subscription.paddle_subscription_id == sid)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if found:
            return found
    user_id = paddle.custom_data_user(data.get("custom_data"))
    if user_id:
        return (
            await db.execute(
                select(Subscription)
                .where(Subscription.user_id == uuid.UUID(user_id))
                .order_by(Subscription.created_at.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
    return None


async def process_event(db: AsyncSession, event: BillingEvent) -> str:
    kind = event.event_type
    data: dict[str, Any] = event.payload.get("data") or {}
    if not kind.startswith("subscription."):
        # transaction.* events are kept for the record; subscription events carry the state.
        event.processed_at = utcnow()
        return "recorded"

    sub = await _find_subscription(db, data)
    if sub is None:
        event.processing_error = (
            "No matching account (unknown subscription and no valid custom_data)."
        )
        event.processed_at = utcnow()
        log.warning("paddle event %s could not be matched", event.paddle_event_id)
        return "unmatched"
    event.subscription_id = sub.id

    if sub.last_event_occurred_at and event.occurred_at <= sub.last_event_occurred_at:
        event.processed_at = utcnow()
        return "stale"

    items = data.get("items") or []
    price = (items[0].get("price") if items else None) or {}
    plan = paddle.plan_for_price(price.get("id"))
    if plan is None:
        event.processing_error = f"Unknown price {price.get('id')!r}; plan left unchanged."
        event.processed_at = utcnow()
        return "unknown_price"

    status = STATUS_MAP.get(str(data.get("status")), sub.status)
    before = effective_plan(sub)
    sub.plan = plan
    sub.status = status
    sub.paddle_subscription_id = data.get("id") or sub.paddle_subscription_id
    sub.paddle_customer_id = data.get("customer_id") or sub.paddle_customer_id
    sub.paddle_price_id = price.get("id")
    sub.paddle_product_id = price.get("product_id")
    cycle = price.get("billing_cycle") or {}
    sub.billing_interval = cycle.get("interval")
    unit = price.get("unit_price") or {}
    sub.unit_price_cents = int(unit["amount"]) if str(unit.get("amount", "")).isdigit() else None
    sub.currency = unit.get("currency_code")
    period = data.get("current_billing_period") or {}
    sub.current_period_start = _ts(period.get("starts_at"))
    sub.current_period_end = _ts(period.get("ends_at"))
    sub.scheduled_change = data.get("scheduled_change") or None
    sub.canceled_at = _ts(data.get("canceled_at"))
    sub.last_event_occurred_at = event.occurred_at
    sub.last_webhook_at = utcnow()

    after = effective_plan(sub)
    changes: list[str] = []
    if ORDER.index(after) < ORDER.index(before):
        await db.flush()
        changes = await apply_plan_constraints(db, sub.user_id)
    audit.record(
        db,
        "billing.subscription_updated",
        actor_user_id=None,
        data={
            "event": event.paddle_event_id,
            "type": kind,
            "plan": plan.value,
            "status": status.value,
            "constraints": changes,
        },
    )
    event.processed_at = utcnow()
    return "applied"


async def set_manual_plan(
    db: AsyncSession, email: str, plan: Plan | None, actor: str
) -> Subscription:
    """Support tool: grant or clear a plan without Paddle (audited)."""
    user = (
        await db.execute(select(User).where(User.email == email.lower(), User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if user is None:
        raise AppError(404, "not_found", f"No user {email}.")
    sub = await _subscription(db, user)
    sub.manual_plan_override = plan
    await db.flush()
    changes = await apply_plan_constraints(db, user.id)
    audit.record(
        db,
        "billing.manual_plan_set",
        actor_user_id=None,
        data={
            "email": email,
            "plan": plan.value if plan else None,
            "by": actor,
            "constraints": changes,
        },
    )
    await db.commit()
    return sub
