from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import AuditLog, Session, Subscription, User, WorkspaceMember
from app.workers.queue import RecordingJobQueue
from tests.conftest import PASSWORD, register_verified


# --------------------------------------------------------------------------- registration
async def test_register_requires_verification_then_verify_logs_in(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    r = await client.post(
        "/auth/register", json={"email": "Nino@Example.com", "password": PASSWORD}
    )
    assert r.status_code == 201
    assert r.json() == {"verification_required": True, "user": None}
    assert "cf_access" not in client.cookies

    r = await client.post("/auth/login", json={"email": "nino@example.com", "password": PASSWORD})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "email_not_verified"

    job = queue.last("send_email")
    assert job["template"] == "verify_email" and job["to"] == "nino@example.com"
    r = await client.post("/auth/verify-email", json={"token": job["params"]["token"]})
    assert r.status_code == 200 and r.json()["email_verified"] is True

    me = await client.get("/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "nino@example.com"

    # Token is single-use.
    r = await client.post("/auth/verify-email", json={"token": job["params"]["token"]})
    assert r.status_code == 400


async def test_register_provisions_workspace_and_free_plan(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "owner@example.com", "Levan Beridze")
    async with SessionLocal() as db:
        user = (await db.execute(select(User))).scalar_one()
        assert user.password_hash and user.password_hash.startswith("$argon2id$")
        member = (await db.execute(select(WorkspaceMember))).scalar_one()
        assert member.user_id == user.id and member.role == "owner"
        sub = (await db.execute(select(Subscription))).scalar_one()
        assert sub.plan == "free" and sub.status == "active"
    ws = (await client.get("/workspaces")).json()
    assert ws[0]["name"] == "Levan's business" and ws[0]["role"] == "owner"


async def test_register_without_verification_signs_in(
    client: httpx.AsyncClient, no_verification: None
) -> None:
    r = await client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    assert r.status_code == 201 and r.json()["verification_required"] is False
    assert (await client.get("/auth/me")).status_code == 200


async def test_duplicate_registration_does_not_leak_when_verification_on(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "dup@example.com")
    r = await client.post("/auth/register", json={"email": "dup@example.com", "password": PASSWORD})
    assert r.status_code == 201 and r.json()["verification_required"] is True
    assert queue.last("send_email")["template"] == "account_exists"


async def test_duplicate_registration_conflict_when_verification_off(
    client: httpx.AsyncClient, no_verification: None
) -> None:
    await client.post("/auth/register", json={"email": "dup@example.com", "password": PASSWORD})
    r = await client.post("/auth/register", json={"email": "DUP@example.com", "password": PASSWORD})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize("password", ["short", "aaaaaaaaaaaaaa", "nino-secret-pass"])
async def test_weak_passwords_rejected(client: httpx.AsyncClient, password: str) -> None:
    r = await client.post(
        "/auth/register", json={"email": "nino@example.com", "password": password}
    )
    assert r.status_code == 422
    assert "password" in r.json()["error"]["details"]["fields"]


# --------------------------------------------------------------------------- login / lockout
async def test_login_wrong_password_then_lockout(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "lock@example.com")
    await client.post("/auth/logout")
    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        r = await client.post(
            "/auth/login", json={"email": "lock@example.com", "password": "nope-nope-nope"}
        )
        assert r.status_code == 401
        assert r.json()["error"]["message"] == "Email or password is incorrect."
    r = await client.post("/auth/login", json={"email": "lock@example.com", "password": PASSWORD})
    assert r.status_code == 429 and "Retry-After" in r.headers
    async with SessionLocal() as db:
        user = (await db.execute(select(User))).scalar_one()
        assert user.locked_until is not None
        actions = (await db.execute(select(AuditLog.action))).scalars().all()
        assert "auth.locked" in actions


async def test_unknown_email_is_rate_limited_the_same_way(client: httpx.AsyncClient) -> None:
    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        r = await client.post(
            "/auth/login", json={"email": "ghost@example.com", "password": "whatever-123"}
        )
        assert r.status_code == 401
    r = await client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": "whatever-123"}
    )
    assert r.status_code == 429


async def test_logout_revokes_session(client: httpx.AsyncClient, queue: RecordingJobQueue) -> None:
    await register_verified(client, queue, "out@example.com")
    access = client.cookies.get("cf_access")
    assert client.cookies.get("cf_signed_in") == "1"
    assert (await client.post("/auth/logout")).status_code == 204
    assert client.cookies.get("cf_signed_in") is None
    assert (await client.get("/auth/me")).status_code == 401
    # Even a copied access token stops working immediately.
    client.cookies.set("cf_access", access)
    assert (await client.get("/auth/me")).status_code == 401


# --------------------------------------------------------------------------- refresh rotation
async def test_refresh_rotates_and_detects_reuse(
    client: httpx.AsyncClient, queue: RecordingJobQueue, monkeypatch: pytest.MonkeyPatch
) -> None:
    await register_verified(client, queue, "rot@example.com")
    old_refresh = client.cookies.get("cf_refresh", path="/api/v1/auth")
    r = await client.post("/auth/refresh")
    assert r.status_code == 204
    new_refresh = client.cookies.get("cf_refresh", path="/api/v1/auth")
    assert new_refresh and new_refresh != old_refresh

    # Within the grace window a stale token is answered with 409, session intact.
    async with httpx.AsyncClient(transport=client._transport, base_url=client.base_url) as other:
        other.cookies.set("cf_refresh", old_refresh, path="/api/v1/auth")
        other.cookies.set("cf_csrf", client.cookies.get("cf_csrf"))
        hdr = {"x-csrf-token": client.cookies.get("cf_csrf")}
        assert (await other.post("/auth/refresh", headers=hdr)).status_code == 409
        assert (await client.get("/auth/me")).status_code == 200

        # After the grace window, replaying the old token is theft: revoke the session.
        monkeypatch.setattr(settings, "REFRESH_REUSE_GRACE_SECONDS", 0)
        r = await other.post("/auth/refresh", headers=hdr)
        assert r.status_code == 401
    assert (await client.get("/auth/me")).status_code == 401
    async with SessionLocal() as db:
        s = (await db.execute(select(Session))).scalar_one()
        assert s.revoked_reason == "reuse_detected"


# --------------------------------------------------------------------------- password reset
async def test_password_reset_flow(
    client: httpx.AsyncClient, queue: RecordingJobQueue, make_client
) -> None:  # type: ignore[no-untyped-def]
    await register_verified(client, queue, "reset@example.com")
    other = await make_client()
    r = await other.post("/auth/password/forgot", json={"email": "reset@example.com"})
    assert r.status_code == 202
    token = queue.last("send_email")["params"]["token"]

    r = await other.post(
        "/auth/password/reset", json={"token": token, "password": "brand-new-password"}
    )
    assert r.status_code == 204
    # Every existing session is revoked.
    assert (await client.get("/auth/me")).status_code == 401
    # Token can't be reused.
    r = await other.post(
        "/auth/password/reset", json={"token": token, "password": "another-password-1"}
    )
    assert r.status_code == 400

    bad = await other.post("/auth/login", json={"email": "reset@example.com", "password": PASSWORD})
    assert bad.status_code == 401
    ok = await other.post(
        "/auth/login", json={"email": "reset@example.com", "password": "brand-new-password"}
    )
    assert ok.status_code == 200
    assert queue.last("send_email")["template"] == "password_changed"


async def test_forgot_password_unknown_email_is_silent(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    r = await client.post("/auth/password/forgot", json={"email": "nobody@example.com"})
    assert r.status_code == 202
    assert not queue.jobs


async def test_change_password_revokes_other_sessions_only(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    make_client,  # type: ignore[no-untyped-def]
) -> None:
    await register_verified(client, queue, "change@example.com")
    laptop = await make_client()
    await laptop.post("/auth/login", json={"email": "change@example.com", "password": PASSWORD})
    assert (await laptop.get("/auth/me")).status_code == 200

    r = await client.post(
        "/auth/password/change",
        json={"current_password": "wrong-password", "new_password": "x-new-password-1"},
    )
    assert r.status_code == 400
    r = await client.post(
        "/auth/password/change",
        json={"current_password": PASSWORD, "new_password": "x-new-password-1"},
    )
    assert r.status_code == 204
    assert (await client.get("/auth/me")).status_code == 200
    assert (await laptop.get("/auth/me")).status_code == 401


async def test_sessions_list_and_revoke(
    client: httpx.AsyncClient, queue: RecordingJobQueue, make_client
) -> None:  # type: ignore[no-untyped-def]
    await register_verified(client, queue, "sess@example.com")
    phone = await make_client()
    await phone.post("/auth/login", json={"email": "sess@example.com", "password": PASSWORD})
    sessions = (await client.get("/auth/sessions")).json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    phone_id = next(s["id"] for s in sessions if not s["current"])
    assert (await client.delete(f"/auth/sessions/{phone_id}")).status_code == 204
    assert (await phone.get("/auth/me")).status_code == 401
    # Can't revoke someone else's (or a non-existent) session.
    assert (await client.delete(f"/auth/sessions/{phone_id}")).status_code == 404


async def test_delete_account(client: httpx.AsyncClient, queue: RecordingJobQueue) -> None:
    await register_verified(client, queue, "bye@example.com")
    r = await client.post("/auth/account/delete", json={"password": "wrong-password"})
    assert r.status_code == 400
    r = await client.post("/auth/account/delete", json={"password": PASSWORD})
    assert r.status_code == 204
    assert (await client.get("/auth/me")).status_code == 401
    r = await client.post("/auth/login", json={"email": "bye@example.com", "password": PASSWORD})
    assert r.status_code == 401
    # The address can be used again.
    r = await client.post("/auth/register", json={"email": "bye@example.com", "password": PASSWORD})
    assert r.status_code == 201 and queue.last("send_email")["template"] == "verify_email"


# --------------------------------------------------------------------------- CSRF / config
async def test_csrf_required_for_unsafe_requests(queue: RecordingJobQueue) -> None:
    from app.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver/api/v1"
    ) as raw:
        r = await raw.post("/auth/login", json={"email": "a@example.com", "password": "x"})
        assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
        token = (await raw.get("/auth/csrf")).json()["csrf_token"]
        r = await raw.post(
            "/auth/login",
            json={"email": "a@example.com", "password": "x"},
            headers={"x-csrf-token": token + "tampered"},
        )
        assert r.status_code == 403
        r = await raw.post(
            "/auth/login",
            json={"email": "a@example.com", "password": "x"},
            headers={"x-csrf-token": token, "origin": "https://evil.example"},
        )
        assert r.status_code == 403


async def test_auth_config_and_google_disabled(client: httpx.AsyncClient) -> None:
    cfg = (await client.get("/auth/config")).json()
    assert cfg == {
        "google_enabled": False,
        "email_verification_required": True,
        "password_min_length": 10,
    }
    assert (await client.get("/auth/google/start")).status_code == 404
