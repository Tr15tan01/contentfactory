"""Dashboard read model. Every number here is a query over stored data — nothing is
estimated, projected or padded."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models import (
    AgentRun,
    AgentStep,
    BusinessProfile,
    Content,
    ContentSchedule,
    MarketingInsight,
    PlatformMetric,
    Publication,
    SocialAccount,
    Workspace,
)
from app.models.enums import (
    AgentRunStatus,
    ContentStatus,
    InsightStatus,
    PublicationStatus,
    ScheduleStatus,
    SocialAccountStatus,
)
from app.schemas.workspace import (
    AgentActivity,
    AttentionItem,
    DashboardOut,
    LearnedInsight,
    PerformanceSummary,
    UpcomingItem,
    WeekStats,
)

# Below this, a comparison is noise; the insight stays hidden until more posts are measured.
MIN_INSIGHT_SAMPLE = 8
PLATFORM_LABEL = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "linkedin": "LinkedIn",
    "pinterest": "Pinterest",
    "x": "X",
}


def _week_bounds(tz_name: str, now: datetime) -> tuple[datetime, datetime]:
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    local = now.astimezone(tz)
    start = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start, start + timedelta(days=7)


async def build_dashboard(db: AsyncSession, ws: Workspace) -> DashboardOut:
    now = utcnow()
    wid = ws.id
    start, end = _week_bounds(ws.timezone, now)

    async def scalar(stmt) -> int:  # type: ignore[no-untyped-def]
        return int((await db.execute(stmt)).scalar() or 0)

    live = and_(Content.workspace_id == wid, Content.deleted_at.is_(None))
    week = WeekStats(
        period_start=start,
        period_end=end,
        created=await scalar(
            select(func.count())
            .select_from(Content)
            .where(live, Content.created_at >= start, Content.created_at < end)
        ),
        published=await scalar(
            select(func.count())
            .select_from(Publication)
            .where(
                Publication.workspace_id == wid,
                Publication.status == PublicationStatus.PUBLISHED,
                Publication.published_at >= start,
                Publication.published_at < end,
            )
        ),
        scheduled=await scalar(
            select(func.count())
            .select_from(ContentSchedule)
            .where(
                ContentSchedule.workspace_id == wid,
                ContentSchedule.status.in_([ScheduleStatus.PENDING, ScheduleStatus.QUEUED]),
                ContentSchedule.scheduled_at >= now,
                ContentSchedule.scheduled_at < end,
            )
        ),
        awaiting_approval=await scalar(
            select(func.count())
            .select_from(Content)
            .where(live, Content.status == ContentStatus.AWAITING_APPROVAL)
        ),
    )

    perf_row = (
        await db.execute(
            select(
                func.count(PlatformMetric.id),
                func.sum(PlatformMetric.reach),
                func.sum(PlatformMetric.views),
                func.sum(
                    func.coalesce(PlatformMetric.likes, 0)
                    + func.coalesce(PlatformMetric.comments, 0)
                    + func.coalesce(PlatformMetric.shares, 0)
                    + func.coalesce(PlatformMetric.saves, 0)
                ),
            )
            .join(Publication, Publication.id == PlatformMetric.publication_id)
            .where(
                PlatformMetric.workspace_id == wid,
                Publication.published_at >= now - timedelta(days=7),
            )
        )
    ).one()
    measured = int(perf_row[0] or 0)
    performance = PerformanceSummary(
        period_days=7,
        posts_measured=measured,
        reach=int(perf_row[1]) if perf_row[1] is not None else None,
        views=int(perf_row[2]) if perf_row[2] is not None else None,
        engagements=int(perf_row[3]) if measured else None,
    )

    upcoming_rows = (
        await db.execute(
            select(ContentSchedule, Content)
            .join(Content, Content.id == ContentSchedule.content_id)
            .where(
                ContentSchedule.workspace_id == wid,
                ContentSchedule.scheduled_at >= now,
                ContentSchedule.status.in_(
                    [ScheduleStatus.PENDING, ScheduleStatus.QUEUED, ScheduleStatus.APPROVAL_OVERDUE]
                ),
                Content.deleted_at.is_(None),
            )
            .order_by(ContentSchedule.scheduled_at)
            .limit(8)
        )
    ).all()
    upcoming = [
        UpcomingItem(
            content_id=c.id,
            title=c.title,
            platform=s.platform.value,
            content_type=c.content_type.value,
            status=c.status.value,
            scheduled_at=s.scheduled_at,
        )
        for s, c in upcoming_rows
    ]

    attention: list[AttentionItem] = []
    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.workspace_id == wid))
    ).scalar_one_or_none()
    if profile is None or profile.onboarding_completed_at is None:
        attention.append(
            AttentionItem(
                kind="finish_onboarding",
                priority="high",
                action_url="/onboarding",
                title="Finish setting up your business",
                description="Your agent needs your business details before it can plan content.",
            )
        )

    overdue = (
        await db.execute(
            select(ContentSchedule, Content)
            .join(Content, Content.id == ContentSchedule.content_id)
            .where(
                ContentSchedule.workspace_id == wid,
                ContentSchedule.status == ScheduleStatus.APPROVAL_OVERDUE,
            )
            .order_by(ContentSchedule.scheduled_at)
            .limit(3)
        )
    ).all()
    for s, c in overdue:
        attention.append(
            AttentionItem(
                kind="approval_overdue",
                priority="high",
                action_url=f"/content/{c.id}",
                title=f"Approval overdue: {c.title}",
                description=f"This {PLATFORM_LABEL[s.platform.value]} post missed its slot because "
                "it wasn't approved. Approve it and pick a new time.",
            )
        )

    pending = (
        (
            await db.execute(
                select(Content)
                .where(live, Content.status == ContentStatus.AWAITING_APPROVAL)
                .order_by(Content.created_at)
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    for c in pending:
        attention.append(
            AttentionItem(
                kind="approve_content",
                priority="normal",
                action_url=f"/content/{c.id}",
                title=f"Approve post: {c.title}",
                description="Review the caption and visual, then approve, edit or reject it.",
            )
        )

    failed = (
        await db.execute(
            select(Publication, Content)
            .join(Content, Content.id == Publication.content_id)
            .where(
                Publication.workspace_id == wid,
                Publication.status == PublicationStatus.FAILED,
                Publication.updated_at >= now - timedelta(days=14),
            )
            .order_by(Publication.updated_at.desc())
            .limit(3)
        )
    ).all()
    for p, c in failed:
        attention.append(
            AttentionItem(
                kind="publication_failed",
                priority="high",
                action_url=f"/content/{c.id}",
                title=f"{PLATFORM_LABEL[p.platform.value]} rejected this publication",
                description=p.error_message or "View details to see what the platform reported.",
            )
        )

    accounts = (
        (
            await db.execute(
                select(SocialAccount).where(
                    SocialAccount.workspace_id == wid, SocialAccount.deleted_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    for a in accounts:
        if a.status in (SocialAccountStatus.EXPIRED, SocialAccountStatus.REVOKED):
            label = PLATFORM_LABEL[a.platform.value]
            attention.append(
                AttentionItem(
                    kind="renew_connection",
                    priority="high",
                    action_url="/settings/social",
                    title=f"Your {label} connection needs to be renewed",
                    description="Scheduled posts for this account are paused until you reconnect.",
                )
            )
    if not any(a.status == SocialAccountStatus.CONNECTED for a in accounts):
        preferred = (profile.preferred_platforms if profile else []) or ["instagram"]
        label = PLATFORM_LABEL.get(str(preferred[0]), "Instagram")
        attention.append(
            AttentionItem(
                kind="connect_account",
                priority="normal",
                action_url="/settings/social",
                title=f"Connect {label}",
                description=f"Connect {label} to let your agent publish content for you.",
            )
        )

    latest_step = (
        select(AgentStep.title)
        .where(AgentStep.run_id == AgentRun.id)
        .order_by(AgentStep.position.desc())
        .limit(1)
        .scalar_subquery()
    )
    agent_rows = (
        await db.execute(
            select(AgentRun, latest_step)
            .where(
                AgentRun.workspace_id == wid,
                AgentRun.status.in_(
                    [AgentRunStatus.RUNNING, AgentRunStatus.QUEUED, AgentRunStatus.NEEDS_INPUT]
                ),
            )
            .order_by(AgentRun.updated_at.desc())
            .limit(5)
        )
    ).all()
    agent = [
        AgentActivity(
            run_id=r.id,
            agent=r.agent.value,
            status=r.status.value,
            goal=r.goal,
            latest_step=step,
            updated_at=r.updated_at,
        )
        for r, step in agent_rows
    ]

    insights = (
        (
            await db.execute(
                select(MarketingInsight)
                .where(
                    MarketingInsight.workspace_id == wid,
                    MarketingInsight.status == InsightStatus.ACTIVE,
                    MarketingInsight.sample_size >= MIN_INSIGHT_SAMPLE,
                )
                .order_by(MarketingInsight.created_at.desc())
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    learned = [
        LearnedInsight(
            id=i.id,
            statement=i.statement,
            sample_size=i.sample_size,
            period_start=i.period_start,
            period_end=i.period_end,
            platform=i.platform.value if i.platform else None,
            confidence=i.confidence.value,
        )
        for i in insights
    ]

    return DashboardOut(
        business_name=profile.name if profile else ws.name,
        is_demo=ws.is_demo,
        week=week,
        performance=performance,
        upcoming=upcoming,
        attention=attention,
        agent=agent,
        learned=learned,
    )
