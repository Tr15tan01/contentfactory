"""Pull post metrics from the platforms on a decaying schedule.

Cadence by post age: every 6 hours for the first 2 days, daily until day 7, weekly until day 30,
then stop. Metrics a platform doesn't report stay NULL; `available_metrics` lists the reported
ones. Every successful pull also appends a MetricSnapshot for trends.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import InvalidToken
from app.core.security import utcnow
from app.models import Content, MetricSnapshot, PlatformMetric, Publication, SocialAccount
from app.models.enums import MetricScope, PublicationStatus, SocialAccountStatus
from app.social import registry
from app.social.base import SocialError
from app.social.service import mark_needs_reauth, token_row, token_set

log = logging.getLogger("contentfactory.metrics")
FIELDS = (
    "impressions",
    "reach",
    "views",
    "likes",
    "comments",
    "shares",
    "saves",
    "clicks",
    "follows",
)


def interval_for(age: timedelta) -> timedelta | None:
    if age < timedelta(days=2):
        return timedelta(hours=6)
    if age < timedelta(days=7):
        return timedelta(days=1)
    if age < timedelta(days=30):
        return timedelta(days=7)
    return None


def engagements(m: PlatformMetric | dict[str, Any]) -> float | None:
    """likes + comments + shares + saves, over whichever of them the platform reports."""
    get = (lambda k: getattr(m, k)) if isinstance(m, PlatformMetric) else m.get
    parts = [get(k) for k in ("likes", "comments", "shares", "saves")]
    known = [float(p) for p in parts if p is not None]
    return sum(known) if known else None


async def collect_due(db: AsyncSession, limit: int = 200) -> dict[str, int]:
    now = utcnow()
    rows = (
        await db.execute(
            select(Publication, PlatformMetric)
            .outerjoin(PlatformMetric, PlatformMetric.publication_id == Publication.id)
            .where(
                Publication.status == PublicationStatus.PUBLISHED,
                Publication.platform_post_id.is_not(None),
                Publication.published_at > now - timedelta(days=30),
                or_(
                    PlatformMetric.id.is_(None), PlatformMetric.synced_at < now - timedelta(hours=6)
                ),
            )
            .order_by(PlatformMetric.synced_at.asc().nulls_first())
            .limit(limit)
        )
    ).all()
    stats = {"collected": 0, "skipped": 0, "failed": 0}
    for pub, metric in rows:
        interval = interval_for(now - pub.published_at) if pub.published_at else None
        if metric and interval and metric.synced_at > now - interval:
            stats["skipped"] += 1
            continue
        try:
            ok = await collect_one(db, pub, metric)
        except Exception:  # one bad post must not stop the batch
            log.exception("metrics failed for %s", pub.id)
            await db.rollback()
            ok = False
        stats["collected" if ok else "failed"] += 1
    return stats


async def collect_one(
    db: AsyncSession, pub: Publication, metric: PlatformMetric | None = None
) -> bool:
    account = await db.get(SocialAccount, pub.social_account_id) if pub.social_account_id else None
    adapter = registry.for_platform(pub.platform)
    content = await db.get(Content, pub.content_id)
    if (
        not account
        or account.status is not SocialAccountStatus.CONNECTED
        or not adapter
        or not content
    ):
        return False
    row = await token_row(db, account.id)
    if row is None:
        return False
    try:
        values = await adapter.fetch_metrics(
            pub.platform,
            account.external_account_id,
            token_set(row),
            pub.platform_post_id or "",
            content.content_type,
        )
    except InvalidToken:
        await mark_needs_reauth(
            db, account, "Stored access couldn't be read. Reconnect the account."
        )
        await db.commit()
        return False
    except SocialError as exc:
        if exc.needs_reauth:
            await mark_needs_reauth(db, account, str(exc))
            await db.commit()
        return False
    if metric is None:
        metric = PlatformMetric(
            workspace_id=pub.workspace_id,
            publication_id=pub.id,
            platform=pub.platform,
            available_metrics=[],
        )
        db.add(metric)
    for f in FIELDS:
        setattr(metric, f, int(values[f]) if f in values else None)
    metric.available_metrics = sorted(k for k in values if k in FIELDS)
    eng = engagements({k: values.get(k) for k in ("likes", "comments", "shares", "saves")})
    reach = values.get("reach") or values.get("views")
    metric.engagement_rate = round(eng / reach, 5) if eng is not None and reach else None
    metric.raw = values
    metric.synced_at = utcnow()
    db.add(
        MetricSnapshot(
            workspace_id=pub.workspace_id,
            scope=MetricScope.PUBLICATION,
            publication_id=pub.id,
            social_account_id=account.id,
            platform=pub.platform,
            metrics=values,
        )
    )
    await db.commit()
    return True
