"""Marketing Intelligence: compare groups of posts and state a finding only with evidence.

For each dimension (pillar, format, time of day, platform) and the first metric with enough
data (saves, engagements, reach, views), the two best-measured groups are compared. A finding
needs at least MIN_GROUP posts in each group, MIN_INSIGHT_SAMPLE in total, and a difference of
at least MIN_LIFT. Otherwise nothing is claimed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.collector import engagements
from app.analytics.service import published_posts
from app.core.security import utcnow
from app.models import MarketingInsight, Workspace
from app.models.enums import Confidence, InsightCategory, InsightStatus
from app.services.dashboard import MIN_INSIGHT_SAMPLE

WINDOW_DAYS = 90
MIN_GROUP = 5
MIN_LIFT = 0.2
METRIC_ORDER = ("saves", "engagements", "reach", "views")
PILLARS = {
    "behind_the_scenes": "behind-the-scenes",
    "educational": "educational",
    "promotional": "promotional",
    "community": "community",
    "product": "product",
    "seasonal": "seasonal",
    "entertainment": "entertaining",
}
FORMATS = {
    "post": "single-photo posts",
    "carousel": "carousels",
    "reel": "Reels",
    "short": "Shorts",
    "story": "Stories",
    "video": "videos",
}


def _time_bucket(hour: int) -> str:
    return (
        "morning"
        if 5 <= hour < 12
        else "afternoon"
        if hour < 17
        else "evening"
        if hour < 22
        else "late night"
    )


def _metric_value(m: Any, metric: str) -> float | None:
    if metric == "engagements":
        return engagements(m)
    v = getattr(m, metric)
    return float(v) if v is not None else None


def _describe(dimension: str, seg: str) -> str:
    if dimension == "pillar":
        return f"{PILLARS.get(seg, seg.replace('_', ' '))} posts"
    if dimension == "format":
        return FORMATS.get(seg, seg)
    if dimension == "time":
        return (
            f"posts published in the {seg}"
            if seg != "late night"
            else "posts published late at night"
        )
    names = {
        "instagram": "Instagram",
        "facebook": "Facebook",
        "tiktok": "TikTok",
        "youtube": "YouTube",
    }
    return f"{names.get(seg, seg.capitalize())} posts"


def _cap(text: str) -> str:
    """Capitalise the first letter only ("TikTok posts" must stay "TikTok")."""
    return text[:1].upper() + text[1:]


CATEGORY = {
    "pillar": InsightCategory.TOPIC,
    "format": InsightCategory.FORMAT,
    "time": InsightCategory.POSTING_TIME,
    "platform": InsightCategory.WORKING,
}


async def analyze(db: AsyncSession, ws: Workspace) -> dict[str, int]:
    posts = await published_posts(db, ws, WINDOW_DAYS)
    tz = ZoneInfo(ws.timezone or "UTC")
    findings: dict[str, dict[str, Any]] = {}
    for dimension in ("pillar", "format", "time", "platform"):
        for metric in METRIC_ORDER:
            groups: dict[str, list[float]] = defaultdict(list)
            for p, c, m in posts:
                if m is None or (value := _metric_value(m, metric)) is None:
                    continue
                seg = {
                    "pillar": c.pillar,
                    "format": c.content_type.value,
                    "time": _time_bucket(p.published_at.astimezone(tz).hour),
                    "platform": p.platform.value,
                }[dimension]
                if seg:
                    groups[seg].append(value)
            eligible = sorted(
                ((k, v) for k, v in groups.items() if len(v) >= MIN_GROUP),
                key=lambda kv: -mean(kv[1]),
            )
            if len(eligible) < 2:
                continue
            (a, va), (b, vb) = eligible[0], eligible[1]
            n = len(va) + len(vb)
            ma, mb = mean(va), mean(vb)
            if n < MIN_INSIGHT_SAMPLE or mb <= 0 or (ma - mb) / mb < MIN_LIFT:
                break  # enough data for this dimension, but no meaningful difference: say nothing
            lift = (ma - mb) / mb
            low = min(len(va), len(vb))
            confidence = (
                Confidence.HIGH
                if low >= 15 and lift >= 0.3
                else Confidence.MEDIUM
                if low >= 8
                else Confidence.LOW
            )
            label = "saves" if metric == "saves" else metric
            da, db_ = _describe(dimension, a), _describe(dimension, b)
            findings[f"{dimension}:{metric}"] = {
                "category": CATEGORY[dimension],
                "metric": metric,
                "segment_a": a,
                "segment_b": b,
                "value_a": round(ma, 2),
                "value_b": round(mb, 2),
                "relative_change": round(lift, 4),
                "sample_size": n,
                "confidence": confidence,
                "title": f"{_cap(da)} outperform {db_}",
                "statement": (
                    f"{_cap(da)} averaged {ma:,.0f} {label} "
                    f"versus {mb:,.0f} for {db_} ({lift:+.0%})."
                ),
                "evidence": {
                    "dimension": dimension,
                    "n_a": len(va),
                    "n_b": len(vb),
                    "groups": {
                        k: {"n": len(v), "mean": round(mean(v), 2)} for k, v in groups.items()
                    },
                },
            }
            break

    now = utcnow()
    existing = {
        i.key: i
        for i in (
            await db.execute(
                select(MarketingInsight).where(
                    MarketingInsight.workspace_id == ws.id, MarketingInsight.key.is_not(None)
                )
            )
        ).scalars()
    }
    stats = {"created": 0, "updated": 0, "superseded": 0}
    for key, f in findings.items():
        insight = existing.get(key)
        if (
            insight
            and insight.status is InsightStatus.DISMISSED
            and insight.updated_at > now - timedelta(days=30)
        ):
            continue  # respect a recent "not useful"
        if insight is None:
            insight = MarketingInsight(
                workspace_id=ws.id, key=key, status=InsightStatus.ACTIVE, evidence={}
            )
            db.add(insight)
            stats["created"] += 1
        else:
            stats["updated"] += 1
            insight.status = (
                InsightStatus.ACTIVE
                if insight.status is not InsightStatus.DISMISSED
                else insight.status
            )
        memory_id = (insight.evidence or {}).get("memory_id")
        for k, v in f.items():
            setattr(insight, k, v)
        if memory_id:
            insight.evidence = {**insight.evidence, "memory_id": memory_id}
        insight.period_start = (now - timedelta(days=WINDOW_DAYS)).date()
        insight.period_end = now.date()
        insight.platform = None
    for key, insight in existing.items():
        if key not in findings and insight.status is InsightStatus.ACTIVE:
            insight.status = InsightStatus.SUPERSEDED  # the data no longer supports it
            stats["superseded"] += 1
    await _log(
        db,
        ws,
        len(posts),
        stats,
        [f["statement"] for k, f in findings.items() if k not in existing],
    )
    await db.commit()
    return stats


async def _log(
    db: AsyncSession, ws: Workspace, n_posts: int, stats: dict[str, int], new: list[str]
) -> None:
    from app.agents import activity
    from app.models.enums import AgentKind, AgentRunStatus, NotificationType
    from app.notifications.service import notify

    run = await activity.start(db, ws.id, AgentKind.ANALYTICS, "Look for patterns in your results")
    await activity.step(
        db,
        run,
        f"Compared {n_posts} published posts from the last {WINDOW_DAYS} days",
        kind="decision",
    )
    summary = f"{stats['created']} new, {stats['updated']} updated, {stats['superseded']} retired"
    await activity.step(
        db, run, summary if any(stats.values()) else "Not enough evidence for a finding yet"
    )
    activity.finish(run, AgentRunStatus.SUCCEEDED, summary)
    for statement in new:
        await notify(
            db,
            workspace_id=ws.id,
            kind=NotificationType.ANALYTICS_INSIGHT,
            title="Your agent learned something new",
            body=statement,
            action_url="/insights",
            dedupe=f"insight:{statement[:80]}",
        )
