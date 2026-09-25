from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, or_

from app.core.database import SessionLocal
from app.core.security import utcnow
from app.models import EmailVerificationToken, PasswordResetToken, Session

log = logging.getLogger("contentfactory.maintenance")


async def purge_expired_auth_rows(ctx: dict[str, Any]) -> dict[str, int]:
    """Nightly: drop expired/used tokens and long-dead sessions."""
    now = utcnow()
    async with SessionLocal() as db:
        counts = {}
        for model in (PasswordResetToken, EmailVerificationToken):
            res = await db.execute(
                delete(model).where(or_(model.expires_at < now, model.used_at.is_not(None)))
            )
            counts[model.__tablename__] = res.rowcount or 0
        res = await db.execute(delete(Session).where(Session.expires_at < now))
        counts["sessions"] = res.rowcount or 0
        await db.commit()
    log.info("purged auth rows: %s", counts)
    return counts
