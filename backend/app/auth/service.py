"""Authentication use-cases. Routers translate results into cookies/HTTP; this module owns
the rules (lockout, rotation, reuse detection, verification, account deletion)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core import rate_limit
from app.core.config import settings
from app.core.errors import AppError, unauthorized
from app.core.redis import get_redis
from app.core.request_context import client_ip, client_ip_for_storage, user_agent
from app.core.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    password_problems,
    utcnow,
    verify_password,
)
from app.models import (
    EmailVerificationToken,
    PasswordResetToken,
    Session,
    Subscription,
    User,
    Workspace,
)
from app.models.enums import Plan, SubscriptionStatus
from app.repositories import users as users_repo
from app.repositories import workspaces as ws_repo
from app.services import audit
from app.workers.queue import JobQueue

INVALID_CREDENTIALS = "Email or password is incorrect."
LOCKED_MESSAGE = "Too many sign-in attempts. Try again in {minutes} minutes."


@dataclass
class IssuedSession:
    session: Session
    access_token: str
    refresh_token: str


@dataclass
class GoogleProfile:
    sub: str
    email: str
    email_verified: bool
    name: str | None
    picture: str | None


def _weak_password(problem: str) -> AppError:
    return AppError(422, "weak_password", problem, {"fields": {"password": problem}})


class AuthService:
    def __init__(self, db: AsyncSession, request: Request, queue: JobQueue) -> None:
        self.db = db
        self.request = request
        self.queue = queue

    # ------------------------------------------------------------------ helpers
    async def _issue_session(self, user: User, method: str) -> IssuedSession:
        user.last_login_at = utcnow()  # every sign-in path issues a session here
        refresh = generate_token()
        session = Session(
            user_id=user.id,
            refresh_token_hash=hash_token(refresh),
            auth_method=method,
            user_agent=user_agent(self.request),
            ip_address=client_ip_for_storage(self.request),
            expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        )
        self.db.add(session)
        await self.db.flush()
        access, _ = create_access_token(user.id, session.id)
        return IssuedSession(session, access, refresh)

    async def _email(self, template: str, user: User, **params: object) -> None:
        await self.queue.enqueue(
            "send_email",
            template=template,
            to=user.email,
            params={"name": user.full_name, **params},
        )

    async def _send_verification(self, user: User) -> None:
        await self.db.execute(
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None)
            )
            .values(used_at=utcnow())
        )
        token = generate_token()
        self.db.add(
            EmailVerificationToken(
                user_id=user.id,
                email=user.email,
                token_hash=hash_token(token),
                expires_at=utcnow() + timedelta(hours=settings.EMAIL_VERIFICATION_TTL_HOURS),
            )
        )
        await self._email("verify_email", user, token=token)

    async def _provision_account(self, user: User) -> Workspace:
        """Every new account gets a workspace and a Free subscription row."""
        first = (user.full_name or "").split(" ")[0]
        ws = await ws_repo.create_workspace(
            self.db, user.id, f"{first}'s business" if first else "My business"
        )
        self.db.add(Subscription(user_id=user.id, plan=Plan.FREE, status=SubscriptionStatus.ACTIVE))
        return ws

    async def revoke_all_sessions(
        self, user_id: uuid.UUID, reason: str, except_id: uuid.UUID | None = None
    ) -> None:
        stmt = (
            update(Session)
            .where(Session.user_id == user_id, Session.revoked_at.is_(None))
            .values(revoked_at=utcnow(), revoked_reason=reason)
        )
        if except_id:
            stmt = stmt.where(Session.id != except_id)
        await self.db.execute(stmt)

    # ------------------------------------------------------------------ register / login
    async def register(
        self, email: str, password: str, full_name: str | None
    ) -> tuple[User | None, IssuedSession | None]:
        email = users_repo.normalize_email(email)
        if problems := password_problems(password, email):
            raise _weak_password(problems[0])

        if existing := await users_repo.get_by_email(self.db, email):
            if settings.AUTH_REQUIRE_EMAIL_VERIFICATION:
                # Same response as success; tell the real owner by email instead.
                await self._email("account_exists", existing)
                return None, None
            raise AppError(
                status.HTTP_409_CONFLICT,
                "email_taken",
                "An account with this email already exists.",
                {"fields": {"email": "An account with this email already exists."}},
            )

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=(full_name or "").strip() or None,
            password_changed_at=utcnow(),
        )
        self.db.add(user)
        await self.db.flush()
        ws = await self._provision_account(user)
        audit.record(
            self.db,
            "auth.register",
            actor_user_id=user.id,
            workspace_id=ws.id,
            request=self.request,
        )

        if settings.AUTH_REQUIRE_EMAIL_VERIFICATION:
            await self._send_verification(user)
            await self.db.commit()
            return user, None
        issued = await self._issue_session(user, "password")
        await self.db.commit()
        return user, issued

    async def login(self, email: str, password: str) -> tuple[User, IssuedSession]:
        email = users_repo.normalize_email(email)
        redis = get_redis()
        allowed, retry = await rate_limit.hit("login-ip", client_ip(self.request), 30, 300)
        if not allowed:
            raise rate_limit.too_many(retry)

        lockout = settings.LOGIN_LOCKOUT_MINUTES
        fail_key = f"login-fail:{rate_limit.identifier_hash(email)}"
        fails = int(await redis.get(fail_key) or 0)
        user = await users_repo.get_by_email(self.db, email)
        now = utcnow()
        if fails >= settings.LOGIN_MAX_ATTEMPTS or (
            user and user.locked_until and user.locked_until > now
        ):
            raise rate_limit.too_many(lockout * 60, LOCKED_MESSAGE.format(minutes=lockout))

        if not verify_password(password, user.password_hash if user else None):
            await redis.incr(fail_key)
            await redis.expire(fail_key, lockout * 60)
            if user:
                user.failed_login_count += 1
                if user.failed_login_count >= settings.LOGIN_MAX_ATTEMPTS:
                    user.locked_until = now + timedelta(minutes=lockout)
                    user.failed_login_count = 0
                    audit.record(
                        self.db, "auth.locked", actor_user_id=user.id, request=self.request
                    )
                audit.record(
                    self.db, "auth.login_failed", actor_user_id=user.id, request=self.request
                )
                await self.db.commit()
            raise unauthorized(INVALID_CREDENTIALS, code="invalid_credentials")

        assert user is not None
        if not user.is_active or user.suspended_at:
            raise AppError(
                403,
                "account_suspended",
                "This account is suspended. Contact support if you think this is a mistake.",
            )
        if settings.AUTH_REQUIRE_EMAIL_VERIFICATION and not user.email_verified_at:
            raise AppError(
                403,
                "email_not_verified",
                "Confirm your email address first. We can send the link again.",
                {"email": user.email},
            )

        await redis.delete(fail_key)
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        if user.password_hash and password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        issued = await self._issue_session(user, "password")
        audit.record(self.db, "auth.login", actor_user_id=user.id, request=self.request)
        await self.db.commit()
        return user, issued

    # ------------------------------------------------------------------ refresh / logout
    async def refresh(self, token: str | None) -> IssuedSession:
        if not token:
            raise unauthorized("Your session ended. Sign in again.", code="session_expired")
        token_hash = hash_token(token)
        now = utcnow()

        session = (
            await self.db.execute(
                select(Session).where(Session.refresh_token_hash == token_hash).with_for_update()
            )
        ).scalar_one_or_none()

        if session is None:
            previous = (
                await self.db.execute(
                    select(Session)
                    .where(Session.previous_refresh_token_hash == token_hash)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if previous and previous.revoked_at is None:
                grace = timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS)
                if previous.rotated_at and now - previous.rotated_at < grace:
                    # Another tab refreshed a moment ago; the browser already has the new cookie.
                    raise AppError(409, "refresh_superseded", "Session was refreshed elsewhere.")
                previous.revoked_at = now
                previous.revoked_reason = "reuse_detected"
                audit.record(
                    self.db,
                    "auth.refresh_reuse",
                    actor_user_id=previous.user_id,
                    request=self.request,
                    entity_type="session",
                    entity_id=previous.id,
                )
                await self.db.commit()
            raise unauthorized("Your session ended. Sign in again.", code="session_expired")

        user = await users_repo.get_by_id(self.db, session.user_id)
        if (
            session.revoked_at
            or session.expires_at <= now
            or user is None
            or not user.is_active
            or user.suspended_at
        ):
            raise unauthorized("Your session ended. Sign in again.", code="session_expired")

        new_refresh = generate_token()
        session.previous_refresh_token_hash = token_hash
        session.refresh_token_hash = hash_token(new_refresh)
        session.rotated_at = now
        session.last_used_at = now
        session.ip_address = client_ip_for_storage(self.request)
        access, _ = create_access_token(user.id, session.id)
        await self.db.commit()
        return IssuedSession(session, access, new_refresh)

    async def logout(self, session_id: uuid.UUID | None, refresh_token: str | None) -> None:
        stmt = update(Session).where(Session.revoked_at.is_(None))
        if session_id:
            stmt = stmt.where(Session.id == session_id)
        elif refresh_token:
            stmt = stmt.where(Session.refresh_token_hash == hash_token(refresh_token))
        else:
            return
        await self.db.execute(stmt.values(revoked_at=utcnow(), revoked_reason="logout"))
        await self.db.commit()

    # ------------------------------------------------------------------ email verification
    async def verify_email(self, token: str) -> tuple[User, IssuedSession]:
        row = (
            await self.db.execute(
                select(EmailVerificationToken)
                .where(EmailVerificationToken.token_hash == hash_token(token))
                .with_for_update()
            )
        ).scalar_one_or_none()
        user = await users_repo.get_by_id(self.db, row.user_id) if row else None
        if (
            row is None
            or user is None
            or row.used_at
            or row.expires_at <= utcnow()
            or row.email != user.email
        ):
            raise AppError(
                400,
                "invalid_token",
                "This confirmation link is invalid or has expired. Request a new one.",
            )
        row.used_at = utcnow()
        user.email_verified_at = user.email_verified_at or utcnow()
        audit.record(self.db, "auth.email_verified", actor_user_id=user.id, request=self.request)
        issued = await self._issue_session(user, "email_link")
        await self.db.commit()
        return user, issued

    async def resend_verification(self, email: str) -> None:
        email = users_repo.normalize_email(email)
        allowed, _ = await rate_limit.hit(
            "verify-email", rate_limit.identifier_hash(email), 3, 3600
        )
        user = await users_repo.get_by_email(self.db, email)
        if allowed and user and not user.email_verified_at:
            await self._send_verification(user)
            await self.db.commit()

    # ------------------------------------------------------------------ passwords
    async def forgot_password(self, email: str) -> None:
        email = users_repo.normalize_email(email)
        allowed, _ = await rate_limit.hit("forgot", rate_limit.identifier_hash(email), 3, 3600)
        user = await users_repo.get_by_email(self.db, email)
        if not (allowed and user and user.is_active and not user.suspended_at):
            return
        token = generate_token()
        self.db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_token(token),
                requested_ip=client_ip_for_storage(self.request),
                expires_at=utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
            )
        )
        audit.record(
            self.db, "auth.password_reset_requested", actor_user_id=user.id, request=self.request
        )
        await self._email("reset_password", user, token=token)
        await self.db.commit()

    async def reset_password(self, token: str, new_password: str) -> None:
        row = (
            await self.db.execute(
                select(PasswordResetToken)
                .where(PasswordResetToken.token_hash == hash_token(token))
                .with_for_update()
            )
        ).scalar_one_or_none()
        user = await users_repo.get_by_id(self.db, row.user_id) if row else None
        if row is None or user is None or row.used_at or row.expires_at <= utcnow():
            raise AppError(
                400,
                "invalid_token",
                "This reset link is invalid or has expired. Request a new one.",
            )
        if problems := password_problems(new_password, user.email):
            raise _weak_password(problems[0])

        now = utcnow()
        await self.db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        user.failed_login_count = 0
        user.locked_until = None
        user.email_verified_at = user.email_verified_at or now  # inbox ownership proven
        await self.revoke_all_sessions(user.id, "password_reset")
        await get_redis().delete(f"login-fail:{rate_limit.identifier_hash(user.email)}")
        audit.record(self.db, "auth.password_reset", actor_user_id=user.id, request=self.request)
        await self._email("password_changed", user)
        await self.db.commit()

    async def change_password(
        self, user: User, session_id: uuid.UUID, current: str | None, new_password: str
    ) -> None:
        if user.password_hash and not verify_password(current or "", user.password_hash):
            raise AppError(
                400,
                "invalid_current_password",
                "Your current password is incorrect.",
                {"fields": {"current_password": "Your current password is incorrect."}},
            )
        if problems := password_problems(new_password, user.email):
            raise _weak_password(problems[0])
        user.password_hash = hash_password(new_password)
        user.password_changed_at = utcnow()
        await self.revoke_all_sessions(user.id, "password_changed", except_id=session_id)
        audit.record(self.db, "auth.password_changed", actor_user_id=user.id, request=self.request)
        await self._email("password_changed", user)
        await self.db.commit()

    # ------------------------------------------------------------------ account deletion
    async def delete_account(
        self, user: User, password: str | None, confirm_email: str | None
    ) -> None:
        if user.password_hash:
            if not verify_password(password or "", user.password_hash):
                raise AppError(
                    400,
                    "invalid_password",
                    "Your password is incorrect.",
                    {"fields": {"password": "Your password is incorrect."}},
                )
        elif users_repo.normalize_email(confirm_email or "") != user.email:
            raise AppError(
                400,
                "confirmation_mismatch",
                "Type your email address to confirm.",
                {"fields": {"confirm_email": "Type your email address to confirm."}},
            )

        now = utcnow()
        original_email = user.email
        await self.db.execute(
            update(Workspace)
            .where(Workspace.owner_id == user.id, Workspace.deleted_at.is_(None))
            .values(deleted_at=now)
        )
        await self.revoke_all_sessions(user.id, "account_deleted")
        user.deleted_at = now
        user.is_active = False
        user.email = f"deleted+{user.id}@deleted.invalid"
        user.password_hash = None
        user.google_sub = None
        user.full_name = None
        user.avatar_url = None
        audit.record(self.db, "auth.account_deleted", actor_user_id=user.id, request=self.request)
        await self.queue.enqueue(
            "send_email", template="account_deleted", to=original_email, params={}
        )
        await self.db.commit()

    # ------------------------------------------------------------------ Google
    async def login_with_google(self, profile: GoogleProfile) -> tuple[User, IssuedSession, bool]:
        if not profile.email_verified:
            raise AppError(
                400,
                "google_email_unverified",
                "Your Google email address isn't verified, so we can't use it to sign in.",
            )
        created = False
        user = await users_repo.get_by_google_sub(self.db, profile.sub)
        if user is None:
            user = await users_repo.get_by_email(self.db, profile.email)
            if user:
                if not user.email_verified_at:
                    # Pre-hijack protection: someone may have registered this address without
                    # owning it. Google proved ownership, so drop the unverified password.
                    user.password_hash = None
                    await self.revoke_all_sessions(user.id, "google_takeover_protection")
                user.google_sub = profile.sub
            else:
                user = User(
                    email=users_repo.normalize_email(profile.email),
                    google_sub=profile.sub,
                    full_name=profile.name,
                    avatar_url=profile.picture,
                )
                self.db.add(user)
                await self.db.flush()
                await self._provision_account(user)
                created = True
        if not user.is_active or user.suspended_at:
            raise AppError(403, "account_suspended", "This account is suspended.")
        user.email_verified_at = user.email_verified_at or utcnow()
        user.avatar_url = user.avatar_url or profile.picture
        user.last_login_at = utcnow()
        issued = await self._issue_session(user, "google")
        audit.record(
            self.db,
            "auth.login_google",
            actor_user_id=user.id,
            request=self.request,
            data={"created": created},
        )
        await self.db.commit()
        return user, issued, created
