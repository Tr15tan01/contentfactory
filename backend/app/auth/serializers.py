from __future__ import annotations

from app.models import Session, User
from app.schemas.auth import SessionOut, UserOut


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified_at is not None,
        has_password=user.password_hash is not None,
        is_superuser=user.is_superuser,
        timezone=user.timezone,
        created_at=user.created_at,
    )


def session_out(session: Session, current_id: object) -> SessionOut:
    return SessionOut(
        id=session.id,
        user_agent=session.user_agent,
        ip_address=str(session.ip_address) if session.ip_address else None,
        auth_method=session.auth_method,
        created_at=session.created_at,
        last_used_at=session.last_used_at,
        current=session.id == current_id,
    )
