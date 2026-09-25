from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDelete, Timestamps, UUIDPk


class User(UUIDPk, Timestamps, SoftDelete, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320))  # stored lower-cased
    email_verified_at: Mapped[datetime | None]
    password_hash: Mapped[str | None] = mapped_column(String(255))  # null for Google-only users
    full_name: Mapped[str | None] = mapped_column(String(120))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    locale: Mapped[str] = mapped_column(String(16), server_default="en")
    timezone: Mapped[str] = mapped_column(String(64), server_default="UTC")

    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    is_superuser: Mapped[bool] = mapped_column(server_default=text("false"))
    suspended_at: Mapped[datetime | None]
    suspended_reason: Mapped[str | None] = mapped_column(String(500))

    failed_login_count: Mapped[int] = mapped_column(server_default="0")
    locked_until: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    password_changed_at: Mapped[datetime | None]

    sessions: Mapped[list[Session]] = relationship(back_populates="user", lazy="noload")

    __table_args__ = (
        # Unique among non-deleted accounts; deleted accounts are anonymised anyway.
        Index(
            "uq_users_email_active",
            func.lower(email),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class Session(UUIDPk, Base):
    """One row per sign-in. The refresh token rotates in place; the previous hash is kept
    briefly so concurrent tabs don't trip reuse detection."""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    previous_refresh_token_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    rotated_at: Mapped[datetime | None]
    auth_method: Mapped[str] = mapped_column(String(16), server_default="password")
    user_agent: Mapped[str | None] = mapped_column(String(400))
    ip_address: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_used_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True)
    revoked_at: Mapped[datetime | None]
    revoked_reason: Mapped[str | None] = mapped_column(String(32))

    user: Mapped[User] = relationship(back_populates="sessions", lazy="noload")


class PasswordResetToken(UUIDPk, Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    requested_ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class EmailVerificationToken(UUIDPk, Base):
    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
