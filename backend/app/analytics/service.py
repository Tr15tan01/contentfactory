"""Analytics over published posts. A total is None when no post in the period reported that
metric, so the UI can say "not available" instead of showing a misleading zero."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.collector import engagements
from app.core.security import utcnow
from app.models import Content, PlatformMetric, Publication, Workspace
from app.models.enums import PublicationStatus

METRICS = ("reach", "views", "likes", "comments", "shares", "saves")


def _sum(values: list[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


async def published_posts(
    db: AsyncSession, ws: Workspace, days: int
) -> list[tuple[Publication, Content, PlatformMetric | None]]:
    since = utcnow() - timedelta(days=days)
    rows = await db.execute(
        select(Publication, Content, PlatformMetric)
        .join(Content, Content.id == Publication.content_id)
        .outerjoin(PlatformMetric, PlatformMetric.publication_id == Publication.id)
        .where(
            Publication.workspace_id == ws.id,
            Publication.status == PublicationStatus.PUBLISHED,
            Publication.published_at >= since,
        )
        .order_by(Publication.published_at)
    )
    return [(p, c, m) for p, c, m in rows.all()]


async def overview(db: AsyncSession, ws: Workspace, days: int) -> dict[str, Any]:
    posts = await published_posts(db, ws, days)
    measured = [(p, c, m) for p, c, m in posts if m is not None]
    totals = {k: _sum([getattr(m, k) for _, _, m in measured]) for k in METRICS}
    totals["engagements"] = _sum([engagements(m) for _, _, m in measured])

    by_platform: dict[str, dict[str, Any]] = {}
    for p, _, m in posts:
        row = by_platform.setdefault(
            p.platform.value,
            {
                "platform": p.platform.value,
                "posts": 0,
                "measured": 0,
                "available": set(),
                **{k: [] for k in (*METRICS, "engagements")},
            },
        )
        row["posts"] += 1
        if m is None:
            continue
        row["measured"] += 1
        row["available"].update(m.available_metrics or [])
        for k in METRICS:
            row[k].append(getattr(m, k))
        row["engagements"].append(engagements(m))
    platforms = [
        {
            **{k: _sum(v[k]) for k in (*METRICS, "engagements")},
            "platform": v["platform"],
            "posts": v["posts"],
            "measured": v["measured"],
            "unavailable": [k for k in METRICS if k not in v["available"]] if v["measured"] else [],
        }
        for v in by_platform.values()
    ]

    tz = ZoneInfo(ws.timezone or "UTC")
    daily: dict[str, dict[str, float]] = defaultdict(lambda: {"posts": 0, "engagements": 0.0})
    start = (utcnow() - timedelta(days=days - 1)).astimezone(tz).date()
    for i in range(days):
        daily[
            (start + timedelta(days=i)).isoformat()
        ]  # every day present, zero posts shown honestly
    for p, _, m in posts:
        day = p.published_at.astimezone(tz).date().isoformat()
        daily[day]["posts"] += 1
        if m is not None and engagements(m) is not None:
            daily[day]["engagements"] += engagements(m) or 0

    ranked = sorted(
        ((p, c, m) for p, c, m in measured if engagements(m) is not None),
        key=lambda t: -(engagements(t[2]) or 0),
    )
    top = [
        {
            "content_id": c.id,
            "title": c.title,
            "platform": p.platform,
            "content_type": c.content_type,
            "pillar": c.pillar,
            "published_at": p.published_at,
            "url": p.platform_url,
            "engagements": engagements(m),
            **{k: getattr(m, k) for k in METRICS},
        }
        for p, c, m in ranked[:5]
    ]
    return {
        "days": days,
        "posts_published": len(posts),
        "posts_measured": len(measured),
        "totals": totals,
        "platforms": platforms,
        "daily": [{"date": d, **v} for d, v in sorted(daily.items())],
        "top_posts": top,
    }
