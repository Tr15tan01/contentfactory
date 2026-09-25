"""Paddle Billing: API client, webhook signature verification, price <-> plan mapping."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx

from app.core.config import settings
from app.models.enums import Plan

API_BASE = {"sandbox": "https://sandbox-api.paddle.com", "production": "https://api.paddle.com"}
SIGNATURE_TOLERANCE_SECONDS = 300


def configured() -> bool:
    return bool(
        settings.PADDLE_API_KEY
        and settings.PADDLE_CLIENT_TOKEN
        and settings.PADDLE_WEBHOOK_SECRET
        and all(price_for_plan(p) for p in (Plan.STARTER, Plan.BUSINESS, Plan.AGENCY))
    )


def price_for_plan(plan: Plan) -> str:
    return {
        Plan.STARTER: settings.PADDLE_STARTER_PRICE_ID,
        Plan.BUSINESS: settings.PADDLE_BUSINESS_PRICE_ID,
        Plan.AGENCY: settings.PADDLE_AGENCY_PRICE_ID,
    }.get(plan, "")


def plan_for_price(price_id: str | None) -> Plan | None:
    for plan in (Plan.STARTER, Plan.BUSINESS, Plan.AGENCY):
        if price_id and price_for_plan(plan) == price_id:
            return plan
    return None


def verify_signature(raw_body: bytes, header: str | None, *, now: float | None = None) -> bool:
    """`Paddle-Signature: ts=<unix>;h1=<hex>[;h1=<hex>]` over `"{ts}:{body}"` (HMAC-SHA256).
    Several h1 values are accepted so the secret can be rotated without downtime."""
    if not header or not settings.PADDLE_WEBHOOK_SECRET:
        return False
    ts, sigs = None, []
    for part in header.split(";"):
        key, _, value = part.strip().partition("=")
        if key == "ts":
            ts = value
        elif key == "h1":
            sigs.append(value)
    if not ts or not ts.isdigit() or not sigs:
        return False
    if abs((now or time.time()) - int(ts)) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(
        settings.PADDLE_WEBHOOK_SECRET.encode(), f"{ts}:".encode() + raw_body, hashlib.sha256
    ).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in sigs)


def sign_custom_data(user_id: str) -> str:
    """Checkout custom_data comes back through the browser; the signature proves we issued it."""
    return hmac.new(
        settings.SESSION_SECRET.encode(), f"paddle-checkout:{user_id}".encode(), hashlib.sha256
    ).hexdigest()[:40]


def custom_data_user(custom: dict[str, Any] | None) -> str | None:
    if not custom:
        return None
    uid, sig = str(custom.get("user_id") or ""), str(custom.get("sig") or "")
    if uid and hmac.compare_digest(sign_custom_data(uid), sig):
        return uid
    return None


class PaddleError(Exception):
    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


class PaddleClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=settings.PADDLE_API_BASE_URL or API_BASE[settings.PADDLE_ENVIRONMENT],
            timeout=20,
        )

    async def _call(
        self, method: str, path: str, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            r = await self._client.request(
                method,
                path,
                json=json,
                headers={
                    "Authorization": f"Bearer {settings.PADDLE_API_KEY}",
                    "Paddle-Version": "1",
                },
            )
        except httpx.HTTPError as exc:
            raise PaddleError("Paddle couldn't be reached. Try again in a moment.") from exc
        if r.status_code >= 400:
            detail = ""
            try:
                detail = r.json().get("error", {}).get("detail", "")
            except ValueError:
                pass
            raise PaddleError(detail or f"Paddle returned an error ({r.status_code}).", 502)
        return dict(r.json().get("data") or {})

    async def change_price(self, subscription_id: str, price_id: str) -> dict[str, Any]:
        return await self._call(
            "PATCH",
            f"/subscriptions/{subscription_id}",
            {
                "items": [{"price_id": price_id, "quantity": 1}],
                "proration_billing_mode": "prorated_immediately",
            },
        )

    async def cancel(self, subscription_id: str) -> dict[str, Any]:
        return await self._call(
            "POST",
            f"/subscriptions/{subscription_id}/cancel",
            {"effective_from": "next_billing_period"},
        )

    async def remove_scheduled_change(self, subscription_id: str) -> dict[str, Any]:
        return await self._call(
            "PATCH", f"/subscriptions/{subscription_id}", {"scheduled_change": None}
        )

    async def portal_url(self, customer_id: str, subscription_id: str | None) -> str:
        body = {"subscription_ids": [subscription_id]} if subscription_id else {}
        data = await self._call("POST", f"/customers/{customer_id}/portal-sessions", body)
        return str(data.get("urls", {}).get("general", {}).get("overview", ""))


_client: PaddleClient | None = None


def get_paddle() -> PaddleClient:
    global _client
    if _client is None:
        _client = PaddleClient()
    return _client


def set_paddle(client: PaddleClient | None) -> None:
    global _client
    _client = client
