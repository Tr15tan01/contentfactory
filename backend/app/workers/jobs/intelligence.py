from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.analytics.collector import collect_due
from app.analytics.insights import analyze
from app.core.database import SessionLocal
from app.intelligence.experiments import evaluate
from app.models import Experiment, Publication, Workspace
from app.models.enums import ExperimentStatus, PublicationStatus

log = logging.getLogger("contentfactory.intelligence")


async def collect_metrics(ctx: dict[str, Any]) -> dict[str, int]:
    async with SessionLocal() as db:
        return await collect_due(db)


async def nightly_intelligence(ctx: dict[str, Any]) -> dict[str, int]:
    """Re-analyse workspaces that published recently, and re-check running experiments."""
    stats = {"workspaces": 0, "experiments": 0}
    async with SessionLocal() as db:
        ws_ids = (
            (
                await db.execute(
                    select(Publication.workspace_id)
                    .where(Publication.status == PublicationStatus.PUBLISHED)
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        for wid in ws_ids:
            ws = await db.get(Workspace, wid)
            if ws is None or ws.deleted_at is not None:
                continue
            try:
                await analyze(db, ws)
                stats["workspaces"] += 1
                for e in (
                    (
                        await db.execute(
                            select(Experiment).where(
                                Experiment.workspace_id == wid,
                                Experiment.status == ExperimentStatus.RUNNING,
                            )
                        )
                    )
                    .scalars()
                    .all()
                ):
                    await evaluate(db, ws, e.id)
                    stats["experiments"] += 1
            except Exception:
                log.exception("intelligence failed for workspace %s", wid)
                await db.rollback()
    return stats


async def approval_reminders(ctx: dict[str, Any]) -> int:
    from app.notifications.reminders import send_reminders

    async with SessionLocal() as db:
        return await send_reminders(db)


async def notification_emails(ctx: dict[str, Any]) -> int:
    from app.notifications.service import send_pending_emails

    async with SessionLocal() as db:
        return await send_pending_emails(db)
