"""Plan catalogue and entitlements — the single source of truth for limits.

Marketing copy on the frontend mirrors these numbers (frontend/lib/plans.ts). Quotas are
monthly and never unlimited.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import Plan


@dataclass(frozen=True)
class PlanLimits:
    plan: Plan
    name: str
    price_usd: int
    businesses: int
    social_accounts: int
    ai_content: int
    images: int
    video_credits: int
    scheduled_posts: int
    autopilot: bool
    auto_publish: bool
    research_agent: bool
    experiments: str  # "none" | "basic" | "full" | "advanced"
    priority_processing: bool


PLANS: dict[Plan, PlanLimits] = {
    Plan.FREE: PlanLimits(
        Plan.FREE,
        "Free",
        0,
        1,
        1,
        10,
        10,
        2,
        10,
        autopilot=False,
        auto_publish=False,
        research_agent=False,
        experiments="none",
        priority_processing=False,
    ),
    Plan.STARTER: PlanLimits(
        Plan.STARTER,
        "Starter",
        19,
        1,
        3,
        60,
        40,
        5,
        100,
        autopilot=False,
        auto_publish=False,
        research_agent=False,
        experiments="basic",
        priority_processing=False,
    ),
    Plan.BUSINESS: PlanLimits(
        Plan.BUSINESS,
        "Business",
        49,
        3,
        8,
        250,
        150,
        20,
        500,
        autopilot=True,
        auto_publish=True,
        research_agent=True,
        experiments="full",
        priority_processing=False,
    ),
    Plan.AGENCY: PlanLimits(
        Plan.AGENCY,
        "Agency",
        99,
        10,
        25,
        700,
        400,
        50,
        2000,
        autopilot=True,
        auto_publish=True,
        research_agent=True,
        experiments="advanced",
        priority_processing=True,
    ),
}


def limits_for(plan: Plan) -> PlanLimits:
    return PLANS[plan]
