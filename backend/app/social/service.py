"""Connecting social accounts: OAuth with signed state, encrypted tokens, plan limits."""

from __future__ import annotations

import json
import logging
import secrets
import time
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.entitlements import effective_plan, user_subscription
from app.billing.plans import PLANS
from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.errors import AppError, not_found
from app.core.security import sign_value, unsign_value, utcnow
from app.models import SocialAccount, SocialAccountToken, User, Workspace
from app.models.enums import Platform, SocialAccountStatus
from app.services import audit
from app.social import registry
from app.social.base import RemoteAccount, SocialError, TokenSet, pkce_pair

log = logging.getLogger("contentfactory.social")
STATE_COOKIE = "cf_oauth_social"
STATE_TTL = 600
PLATFORM_LABEL = {
    Platform.INSTAGRAM: "Instagram",
    Platform.FACEBOOK: "Facebook",
    Platform.TIKTOK: "TikTok",
    Platform.YOUTUBE: "YouTube",
}


def redirect_uri(provider: str) -> str:
    return f"{settings.APP_URL.rstrip('/')}{settings.API_PREFIX}/social/callback/{provider}"


def providers(connected: dict[Platform, int]) -> list[dict[str, Any]]:
    out = []
    for name, a in registry.adapters().items():
        out.append(
            {
                "provider": name,
                "label": a.label,
                "platforms": [p.value for p in a.platforms],
                "configured": a.configured(),
                "connected": sum(connected.get(p, 0) for p in a.platforms),
            }
        )
    return out


async def connected_counts(db: AsyncSession, ws: Workspace) -> dict[Platform, int]:
    rows = await db.execute(
        select(SocialAccount.platform, func.count())
        .where(SocialAccount.workspace_id == ws.id, SocialAccount.deleted_at.is_(None))
        .group_by(SocialAccount.platform)
    )
    return {p: c for p, c in rows.all()}


def start_connect(ws: Workspace, user: User, provider: str) -> tuple[str, str]:
    """Returns (authorize_url, signed state cookie value)."""
    adapter = registry.adapter(provider)
    if adapter is None:
        raise not_found("Provider")
    if not adapter.configured():
        raise AppError(
            503, "provider_unavailable", f"{adapter.label} isn't configured on this server yet."
        )
    verifier, _ = pkce_pair()
    nonce = secrets.token_urlsafe(24)
    payload = {
        "p": provider,
        "w": str(ws.id),
        "u": str(user.id),
        "v": verifier,
        "n": nonce,
        "e": int(time.time()) + STATE_TTL,
    }
    cookie = sign_value(json.dumps(payload, separators=(",", ":")))
    return adapter.authorize_url(nonce, verifier, redirect_uri(provider)), cookie


def read_state(cookie: str | None, state: str | None, provider: str) -> dict[str, Any]:
    raw = unsign_value(cookie or "")
    if not raw or not state:
        raise SocialError("The connection request expired. Start again.", code="state_invalid")
    data = json.loads(raw)
    if (
        data.get("p") != provider
        or not secrets.compare_digest(str(data.get("n")), state)
        or int(data.get("e", 0)) < time.time()
    ):
        raise SocialError("The connection request expired. Start again.", code="state_invalid")
    return data


async def _account_limit(db: AsyncSession, ws: Workspace) -> tuple[int, int]:
    """Connected accounts across every workspace this owner has, against the plan limit."""
    plan = PLANS[effective_plan(await user_subscription(db, ws.owner_id))]
    used = (
        await db.execute(
            select(func.count())
            .select_from(SocialAccount)
            .join(Workspace, Workspace.id == SocialAccount.workspace_id)
            .where(
                Workspace.owner_id == ws.owner_id,
                Workspace.deleted_at.is_(None),
                SocialAccount.deleted_at.is_(None),
                SocialAccount.status.in_(
                    [SocialAccountStatus.CONNECTED, SocialAccountStatus.EXPIRED]
                ),
            )
        )
    ).scalar_one()
    return used, plan.social_accounts


def _store_tokens(
    db: AsyncSession, account: SocialAccount, token: TokenSet, existing: SocialAccountToken | None
) -> None:
    row = existing or SocialAccountToken(social_account_id=account.id)
    row.access_token_encrypted = encrypt(token.access_token)
    row.refresh_token_encrypted = encrypt(token.refresh_token) if token.refresh_token else None
    row.expires_at = token.expires_at
    row.refresh_expires_at = token.refresh_expires_at
    row.token_type = "bearer"  # noqa: S105 - a token *type* label, not a secret
    if existing is None:
        db.add(row)


async def token_row(db: AsyncSession, account_id: uuid.UUID) -> SocialAccountToken | None:
    return (
        await db.execute(
            select(SocialAccountToken).where(SocialAccountToken.social_account_id == account_id)
        )
    ).scalar_one_or_none()


def token_set(row: SocialAccountToken) -> TokenSet:
    return TokenSet(
        access_token=decrypt(row.access_token_encrypted),
        refresh_token=decrypt(row.refresh_token_encrypted) if row.refresh_token_encrypted else None,
        expires_at=row.expires_at,
        refresh_expires_at=row.refresh_expires_at,
    )


async def finish_connect(
    db: AsyncSession, provider: str, code: str, state_data: dict[str, Any]
) -> dict[str, int]:
    """Exchange the code and save every eligible account, within the plan's account limit.
    Reconnecting an existing account always works (and refreshes its tokens)."""
    adapter = registry.adapter(provider)
    ws = await db.get(Workspace, uuid.UUID(state_data["w"]))
    if adapter is None or ws is None or ws.deleted_at is not None:
        raise SocialError("That workspace no longer exists.", code="workspace_missing")
    remote: list[RemoteAccount] = await adapter.connect(
        code, state_data["v"], redirect_uri(provider)
    )
    if not remote:
        raise SocialError("No eligible accounts were found on that login.", code="no_accounts")

    used, limit = await _account_limit(db, ws)
    connected = reconnected = skipped = 0
    for r in remote:
        existing = (
            await db.execute(
                select(SocialAccount).where(
                    SocialAccount.workspace_id == ws.id,
                    SocialAccount.platform == r.platform,
                    SocialAccount.external_account_id == r.external_id,
                )
            )
        ).scalar_one_or_none()
        is_new = (
            existing is None
            or existing.deleted_at is not None
            or existing.status is SocialAccountStatus.REVOKED
        )
        if is_new and used >= limit:
            skipped += 1
            continue
        account = existing or SocialAccount(
            workspace_id=ws.id, platform=r.platform, external_account_id=r.external_id
        )
        account.status = SocialAccountStatus.CONNECTED
        account.deleted_at = None
        account.display_name, account.username, account.avatar_url = (
            r.display_name,
            r.username,
            r.avatar_url,
        )
        account.scopes, account.capabilities = r.token.scopes, r.capabilities
        account.connected_by_id = uuid.UUID(state_data["u"])
        account.last_error, account.last_synced_at = None, utcnow()
        if existing is None:
            db.add(account)
        await db.flush()
        _store_tokens(db, account, r.token, await token_row(db, account.id))
        if is_new:
            used += 1
            connected += 1
        else:
            reconnected += 1
    audit.record(
        db,
        "social.connected",
        actor_user_id=uuid.UUID(state_data["u"]),
        workspace_id=ws.id,
        data={
            "provider": provider,
            "connected": connected,
            "reconnected": reconnected,
            "skipped": skipped,
        },
    )
    await db.commit()
    return {"connected": connected, "reconnected": reconnected, "skipped": skipped}


async def list_accounts(
    db: AsyncSession, ws: Workspace
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = await db.execute(
        select(SocialAccount, SocialAccountToken.expires_at)
        .outerjoin(SocialAccountToken, SocialAccountToken.social_account_id == SocialAccount.id)
        .where(SocialAccount.workspace_id == ws.id, SocialAccount.deleted_at.is_(None))
        .order_by(SocialAccount.platform, SocialAccount.display_name)
    )
    used, limit = await _account_limit(db, ws)
    return [
        {
            "id": a.id,
            "platform": a.platform,
            "status": a.status,
            "display_name": a.display_name,
            "username": a.username,
            "avatar_url": a.avatar_url,
            "last_error": a.last_error,
            "token_expires_at": exp,
            "connected_at": a.created_at,
            "capabilities": a.capabilities,
        }
        for a, exp in rows.all()
    ], {"used": used, "limit": limit}


async def disconnect(db: AsyncSession, ws: Workspace, user: User, account_id: uuid.UUID) -> None:
    account = await db.get(SocialAccount, account_id)
    if account is None or account.workspace_id != ws.id or account.deleted_at is not None:
        raise not_found("Account")
    row = await token_row(db, account.id)
    if row is not None:
        await db.delete(row)  # tokens are removed, not just hidden
    account.status = SocialAccountStatus.REVOKED
    account.deleted_at = utcnow()
    audit.record(
        db,
        "social.disconnected",
        actor_user_id=user.id,
        workspace_id=ws.id,
        data={"platform": account.platform.value, "account": account.display_name},
    )
    await db.commit()


async def mark_needs_reauth(db: AsyncSession, account: SocialAccount, message: str) -> None:
    account.status = SocialAccountStatus.EXPIRED
    account.last_error = message[:1000]


async def refresh_due_tokens(db: AsyncSession) -> dict[str, int]:
    """Hourly: refresh tokens that expire within a day. Failures flag the account for reconnect."""
    soon = utcnow() + timedelta(hours=24)
    rows = (
        await db.execute(
            select(SocialAccount, SocialAccountToken)
            .join(SocialAccountToken, SocialAccountToken.social_account_id == SocialAccount.id)
            .where(
                SocialAccount.deleted_at.is_(None),
                SocialAccount.status == SocialAccountStatus.CONNECTED,
                SocialAccountToken.expires_at.is_not(None),
                SocialAccountToken.expires_at < soon,
            )
        )
    ).all()
    stats = {"refreshed": 0, "expired": 0, "failed": 0}
    for account, row in rows:
        adapter = registry.for_platform(account.platform)
        if adapter is None:
            continue
        try:
            fresh = await adapter.refresh(token_set(row))
        except SocialError as exc:
            if exc.needs_reauth:
                await mark_needs_reauth(db, account, str(exc))
                stats["expired"] += 1
            else:
                stats["failed"] += 1  # transient: next run tries again
            continue
        if fresh is None:
            if row.expires_at and row.expires_at < utcnow():
                await mark_needs_reauth(db, account, "Access expired. Reconnect the account.")
                stats["expired"] += 1
            continue
        _store_tokens(db, account, fresh, row)
        stats["refreshed"] += 1
    await db.commit()
    return stats
