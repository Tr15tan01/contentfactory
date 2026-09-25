from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(
        func.lower(User.email) == normalize_email(email), User.deleted_at.is_(None)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    user = await db.get(User, user_id)
    return user if user and user.deleted_at is None else None


async def get_by_google_sub(db: AsyncSession, sub: str) -> User | None:
    stmt = select(User).where(User.google_sub == sub, User.deleted_at.is_(None))
    return (await db.execute(stmt)).scalar_one_or_none()
