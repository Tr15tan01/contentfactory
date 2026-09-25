"""Seed a clearly-marked demo workspace: Tbilisi Coffee Lab.

    python -m scripts.seed_demo            # create (idempotent: replaces the previous demo)
    python -m scripts.seed_demo --remove   # delete demo data

Demo data lives only in workspaces with is_demo = true. The publishing and analytics workers
skip demo workspaces, and the UI labels them. Refuses to run when ENVIRONMENT=production.
Metrics are synthetic but internally consistent: the insight below is *computed* from them.
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from statistics import mean
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from app.ai.embeddings import embed
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    AgentRun,
    AgentStep,
    Brand,
    BusinessProfile,
    Content,
    ContentSchedule,
    ContentVariant,
    MarketingInsight,
    MarketingMemory,
    PlatformMetric,
    Product,
    Publication,
    SocialAccount,
    Subscription,
    User,
    Workspace,
    WorkspaceMember,
)
from app.models.enums import (
    AgentKind,
    AgentRunStatus,
    AgentTrigger,
    Confidence,
    ContentOrigin,
    ContentStatus,
    ContentType,
    InsightCategory,
    InsightStatus,
    MemoryCategory,
    MemorySource,
    Plan,
    Platform,
    PublicationStatus,
    ScheduleStatus,
    SocialAccountStatus,
    SubscriptionStatus,
    WorkspaceRole,
)
from app.repositories.workspaces import DEFAULT_WORKSPACE_SETTINGS
from scripts.demo_media import delete_media_files, seed_media

DEMO_EMAIL = "demo@contentfactory.dev"
MEMORY_TEXT = "Educational explainers (how-to, origin stories) earn more saves than offers."
DEMO_PASSWORD = "demo-coffee-2026"
TZ = ZoneInfo("Asia/Tbilisi")

EDUCATIONAL = [
    (
        "How we dial in espresso every morning",
        "Why the first shot of the day always gets tasted, not served",
    ),
    ("Cold brew vs iced coffee", "Two drinks, two methods — and why one takes 18 hours"),
    (
        "3 mistakes people make with milk foam",
        "Most of them happen before the steam wand even starts",
    ),
    ("Where our beans come from", "Meet the Huila farm behind this month's filter"),
    ("What 'single origin' actually means", "A 60-second explainer with our head roaster"),
    ("How to store coffee at home", "Spoiler: not in the freezer door"),
    ("Latte art: the heart, step by step", "Our barista slows it down so you can follow along"),
    ("Why our cappuccino is smaller", "Ratios, texture, and a little Italian stubbornness"),
]
PROMOTIONAL = [
    ("Cold brew is back for summer", "Bottled 330 ml, only at the Vake bar"),
    ("New: cardamom bun", "Baked every morning at 7 with Georgian honey"),
    ("Weekday breakfast combo", "Cappuccino + pastry for 12 GEL until 11:00"),
    ("Loyalty card: 10th coffee free", "Ask for a card at the counter"),
    ("Saturday cupping session", "Taste four origins with our roaster, 12:00"),
    ("Gift bags for Tbilisoba", "Beans, a mug and a handwritten note"),
]


def _at(day: datetime, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day.date(), time(hour, minute), tzinfo=TZ).astimezone(UTC)


async def remove(db) -> None:  # type: ignore[no-untyped-def]
    demo_ids = (
        (await db.execute(select(Workspace.id).where(Workspace.is_demo.is_(True)))).scalars().all()
    )
    if demo_ids:
        await delete_media_files(db, list(demo_ids))
        await db.execute(delete(Workspace).where(Workspace.id.in_(demo_ids)))
    await db.execute(delete(User).where(User.email == DEMO_EMAIL))
    await db.commit()


async def seed() -> None:
    if settings.is_production:
        sys.exit("Refusing to seed demo data in production.")
    rng = random.Random(2026)
    now = datetime.now(UTC)
    local_now = now.astimezone(TZ)
    week_start = (local_now - timedelta(days=local_now.weekday())).replace(hour=0, minute=0)

    async with SessionLocal() as db:
        await remove(db)

        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            full_name="Nino Kapanadze",
            email_verified_at=now,
            timezone="Asia/Tbilisi",
        )
        db.add(user)
        await db.flush()
        db.add(
            Subscription(
                user_id=user.id,
                plan=Plan.BUSINESS,
                status=SubscriptionStatus.ACTIVE,
                unit_price_cents=4900,
                currency="USD",
                billing_interval="month",
                current_period_start=now - timedelta(days=9),
                current_period_end=now + timedelta(days=21),
            )
        )
        ws = Workspace(
            name="Tbilisi Coffee Lab",
            slug="tbilisi-coffee-lab-demo",
            owner_id=user.id,
            timezone="Asia/Tbilisi",
            is_demo=True,
            settings=DEFAULT_WORKSPACE_SETTINGS,
        )
        db.add(ws)
        await db.flush()
        db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER))

        db.add(
            BusinessProfile(
                workspace_id=ws.id,
                name="Tbilisi Coffee Lab",
                industry="Specialty coffee shop",
                description="Small-batch roaster and café in Vake. We roast twice a week and teach "
                "people how to brew better coffee at home.",
                location="Vake, Tbilisi, Georgia",
                website="https://tbilisicoffeelab.example",
                preferred_language="en",
                content_style="Warm, curious, a little nerdy about coffee",
                posting_frequency="4 posts per week",
                audience={
                    "description": "Young professionals and students in Vake and Saburtalo",
                    "age_range": "22-40",
                    "interests": ["specialty coffee", "brunch", "remote work"],
                    "problems": ["bad office coffee", "no quiet place to work"],
                    "buying_intent": "Daily habit; weekend treats",
                },
                unique_selling_points=[
                    "Roasted in-house twice a week",
                    "Baristas trained in Milan",
                    "Quiet upstairs room for laptop work",
                ],
                competitors=["Coffeesta", "Black Cup"],
                marketing_goals=["engagement", "followers", "bookings"],
                preferred_platforms=["instagram", "tiktok"],
                topics_to_avoid=["politics", "discount wars with neighbours"],
                onboarding_step=6,
                onboarding_completed_at=now - timedelta(days=30),
            )
        )
        db.add(
            Brand(
                workspace_id=ws.id,
                voice="Friendly expert. Explains, never lectures.",
                tone=["warm", "curious", "precise"],
                colors=["#2B1D14", "#C8894B", "#F3E9DC"],
                fonts=["Fraunces", "Inter"],
                visual_style="Natural light, close-ups of hands and cups, wooden counters",
            )
        )
        for i, (name, price, desc) in enumerate(
            [
                ("Espresso", "5.00", "Our house blend, pulled 1:2 in 28 seconds"),
                ("Cappuccino", "8.00", "Double shot, 150 ml, silky microfoam"),
                ("Cold Brew", "9.00", "18-hour steep, bottled daily"),
                ("Pastries", "6.00", "Cardamom buns and croissants baked every morning"),
            ]
        ):
            db.add(
                Product(
                    workspace_id=ws.id,
                    name=name,
                    price=Decimal(price),
                    currency="GEL",
                    description=desc,
                    position=i,
                )
            )

        accounts = {}
        for platform, username in (
            (Platform.INSTAGRAM, "tbilisicoffeelab"),
            (Platform.TIKTOK, "tbilisicoffeelab"),
        ):
            acc = SocialAccount(
                workspace_id=ws.id,
                platform=platform,
                status=SocialAccountStatus.CONNECTED,
                external_account_id=f"demo-{platform.value}",
                username=username,
                display_name="Tbilisi Coffee Lab",
                capabilities={"demo": True},
                connected_by_id=user.id,
            )
            db.add(acc)
            accounts[platform] = acc
        await db.flush()

        # ---- 30 days of published history with synthetic metrics --------------------------
        posts = [(t, h, "educational") for t, h in EDUCATIONAL] + [
            (t, h, "promotional") for t, h in PROMOTIONAL
        ]
        rng.shuffle(posts)
        saves: dict[str, list[int]] = {"educational": [], "promotional": []}
        for i, (title, hook, pillar) in enumerate(posts):
            day = local_now - timedelta(days=29 - i * 2)
            platform = Platform.INSTAGRAM if i % 3 else Platform.TIKTOK
            ctype = (
                ContentType.REEL
                if pillar == "educational" and i % 2
                else (ContentType.CAROUSEL if pillar == "educational" else ContentType.POST)
            )
            published_at = _at(day, rng.choice([9, 13, 18]))
            if published_at >= now:
                continue
            c = Content(
                workspace_id=ws.id,
                status=ContentStatus.PUBLISHED,
                content_type=ctype,
                origin=ContentOrigin.AI,
                title=title,
                hook=hook,
                pillar=pillar,
                caption=f"{hook}.",
                cta="Save this for your next coffee",
                attributes={"pillar": pillar, "format": ctype.value},
                approved_by_id=user.id,
                approved_at=published_at - timedelta(days=1),
                created_at=published_at - timedelta(days=2),
            )
            db.add(c)
            await db.flush()
            db.add(
                ContentVariant(
                    content_id=c.id,
                    platform=platform,
                    caption=f"{hook}.\n\nSave this for your next coffee.",
                    hashtags=["TbilisiCoffeeLab", "SpecialtyCoffee", "Tbilisi"],
                    cta="Save this for your next coffee",
                )
            )
            pub = Publication(
                workspace_id=ws.id,
                content_id=c.id,
                platform=platform,
                social_account_id=accounts[platform].id,
                idempotency_key=f"demo:{c.id}:{platform.value}",
                status=PublicationStatus.PUBLISHED,
                scheduled_at=published_at,
                published_at=published_at,
                platform_post_id=f"demo-{i}",
            )
            db.add(pub)
            await db.flush()
            base = 900 if pillar == "educational" else 700
            reach = int(rng.gauss(base, 180))
            s = max(
                3,
                int(reach * (0.045 if pillar == "educational" else 0.022) * rng.uniform(0.8, 1.2)),
            )
            saves[pillar].append(s)
            is_video = ctype == ContentType.REEL or platform == Platform.TIKTOK
            db.add(
                PlatformMetric(
                    workspace_id=ws.id,
                    publication_id=pub.id,
                    platform=platform,
                    reach=reach,
                    impressions=int(reach * 1.4),
                    likes=int(reach * 0.07),
                    comments=int(reach * 0.008),
                    shares=int(reach * 0.01),
                    saves=s,
                    views=int(reach * 1.6) if is_video else None,
                    available_metrics=[
                        "reach",
                        "impressions",
                        "likes",
                        "comments",
                        "shares",
                        "saves",
                    ]
                    + (["views"] if is_video else []),
                    raw={"demo": True},
                )
            )

        # Insight computed from the rows above.
        edu, promo = mean(saves["educational"]), mean(saves["promotional"])
        lift = (edu - promo) / promo
        n = len(saves["educational"]) + len(saves["promotional"])
        db.add(
            MarketingInsight(
                workspace_id=ws.id,
                category=InsightCategory.FORMAT,
                status=InsightStatus.ACTIVE,
                title="Educational posts get saved more",
                statement=f"Educational posts averaged {edu:.0f} saves versus {promo:.0f} for "
                f"promotional posts over the last 30 days ({lift:+.0%}).",
                metric="saves",
                segment_a="educational",
                segment_b="promotional",
                value_a=edu,
                value_b=promo,
                relative_change=lift,
                sample_size=n,
                period_start=(now - timedelta(days=30)).date(),
                period_end=now.date(),
                confidence=Confidence.MEDIUM if n >= 12 else Confidence.LOW,
                evidence={
                    "dimension": "pillar",
                    "n_a": len(saves["educational"]),
                    "n_b": len(saves["promotional"]),
                },
                key="pillar:saves",
            )
        )
        db.add(
            MarketingMemory(
                workspace_id=ws.id,
                category=MemoryCategory.SUCCESSFUL_FORMAT,
                source=MemorySource.ANALYTICS,
                content=MEMORY_TEXT,
                evidence={"metric": "saves"},
                embedding=(await embed([MEMORY_TEXT]))[0],
            )
        )

        # ---- This week: approvals, schedule, a draft ---------------------------------------
        upcoming = [
            (
                "5 mistakes people make when brewing at home",
                ContentStatus.AWAITING_APPROVAL,
                ContentType.CAROUSEL,
                Platform.INSTAGRAM,
                3,
                18,
            ),
            (
                "Behind the roaster: Tuesday batch",
                ContentStatus.AWAITING_APPROVAL,
                ContentType.REEL,
                Platform.INSTAGRAM,
                4,
                9,
            ),
            (
                "Cold brew in 18 hours, in 15 seconds",
                ContentStatus.SCHEDULED,
                ContentType.REEL,
                Platform.TIKTOK,
                5,
                13,
            ),
            (
                "Cardamom bun, fresh at 7",
                ContentStatus.SCHEDULED,
                ContentType.POST,
                Platform.INSTAGRAM,
                6,
                8,
            ),
            (
                "Espresso ratios explained",
                ContentStatus.APPROVED,
                ContentType.CAROUSEL,
                Platform.INSTAGRAM,
                8,
                18,
            ),
        ]
        for title, status, ctype, platform, offset, hour in upcoming:
            when = _at(week_start + timedelta(days=offset), hour)
            if when <= now:
                when = now + timedelta(days=offset % 3 + 1, hours=hour % 5)
            c = Content(
                workspace_id=ws.id,
                status=status,
                content_type=ctype,
                origin=ContentOrigin.AI,
                title=title,
                pillar="educational",
                hook=title,
                caption=f"{title}. Save it for later.",
                attributes={"pillar": "educational", "format": ctype.value},
                approved_by_id=user.id if status != ContentStatus.AWAITING_APPROVAL else None,
                approved_at=now if status != ContentStatus.AWAITING_APPROVAL else None,
            )
            db.add(c)
            await db.flush()
            db.add(
                ContentVariant(
                    content_id=c.id,
                    platform=platform,
                    caption=f"{title}.\n\nSave it for later, and tell us how yours turns out.",
                    hashtags=["TbilisiCoffeeLab", "CoffeeTips", "Tbilisi"],
                    cta="Save it for later",
                )
            )
            approved = status in (ContentStatus.APPROVED, ContentStatus.SCHEDULED)
            db.add(
                ContentSchedule(
                    workspace_id=ws.id,
                    content_id=c.id,
                    platform=platform,
                    social_account_id=accounts[platform].id,
                    scheduled_at=when,
                    status=ScheduleStatus.QUEUED if approved else ScheduleStatus.PENDING,
                )
            )
        idea = Content(
            workspace_id=ws.id,
            status=ContentStatus.DRAFT,
            content_type=ContentType.POST,
            origin=ContentOrigin.IDEA,
            title="Rainy day filter recommendations",
            attributes={"version": 1},
        )
        db.add(idea)
        await db.flush()
        db.add(
            ContentVariant(content_id=idea.id, platform=Platform.INSTAGRAM, caption="", hashtags=[])
        )

        # ---- Agent activity ----------------------------------------------------------------
        done = AgentRun(
            workspace_id=ws.id,
            agent=AgentKind.CONTENT,
            trigger=AgentTrigger.SCHEDULE,
            status=AgentRunStatus.SUCCEEDED,
            goal="Create this week's drafts",
            summary="Created 3 drafts and scheduled 2 approved posts.",
            max_steps=20,
            max_runtime_seconds=600,
            max_cost_usd=Decimal("0.50"),
            steps_taken=4,
            cost_usd=Decimal("0.0840"),
            started_at=now - timedelta(hours=20),
            finished_at=now - timedelta(hours=20),
        )
        running = AgentRun(
            workspace_id=ws.id,
            agent=AgentKind.RESEARCH,
            trigger=AgentTrigger.SCHEDULE,
            status=AgentRunStatus.RUNNING,
            goal="Research next week's topics",
            max_steps=15,
            max_runtime_seconds=900,
            max_cost_usd=Decimal("0.40"),
            steps_taken=2,
            cost_usd=Decimal("0.0210"),
            started_at=now - timedelta(minutes=4),
        )
        db.add_all([done, running])
        await db.flush()
        for run, steps in (
            (
                done,
                [
                    "Loaded brand memory and last 30 days of results",
                    "Selected 5 topics from the educational pillar",
                    "Content Agent created 3 drafts",
                    "Creative Agent chose uploaded product photos for 2 posts",
                ],
            ),
            (
                running,
                [
                    "Checked cached research from last week",
                    "Looking for seasonal topics around Tbilisoba",
                ],
            ),
        ):
            for pos, title in enumerate(steps):
                db.add(
                    AgentStep(
                        run_id=run.id,
                        position=pos,
                        kind="ai_call",
                        title=title,
                        status=AgentRunStatus.SUCCEEDED
                        if run is done or pos == 0
                        else AgentRunStatus.RUNNING,
                        started_at=(run.started_at or now) + timedelta(seconds=40 * pos),
                    )
                )
        await db.commit()
        media = await seed_media(db, ws, user.id)
    print(f"Demo workspace ready ({media} photos). Sign in as {DEMO_EMAIL} / {DEMO_PASSWORD}")


async def main() -> None:
    if "--remove" in sys.argv:
        async with SessionLocal() as db:
            await remove(db)
        print("Demo data removed.")
    else:
        await seed()


if __name__ == "__main__":
    asyncio.run(main())
