"""The frontend's plan copy (frontend/lib/plans.ts) must match the backend catalogue.

Enforcement lives in the backend; this test stops pricing pages from advertising limits the
product doesn't grant. Skipped when the frontend isn't checked out next to the backend.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.billing.plans import PLANS

PLANS_TS = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "plans.ts"

FIELDS = {
    "priceUsd": "price_usd",
    "businesses": "businesses",
    "socialAccounts": "social_accounts",
    "aiContent": "ai_content",
    "images": "images",
    "videoCredits": "video_credits",
    "scheduledPosts": "scheduled_posts",
    "autopilot": "autopilot",
    "autoPublish": "auto_publish",
    "researchAgent": "research_agent",
    "experiments": "experiments",
    "priorityProcessing": "priority_processing",
}


def _parse_ts() -> dict[str, dict[str, object]]:
    source = PLANS_TS.read_text()
    plans: dict[str, dict[str, object]] = {}
    for block in re.split(r"\n  \{\n", source)[1:]:
        m = re.search(r'id: "(\w+)"', block)
        if not m:
            continue
        values: dict[str, object] = {}
        for ts_key in FIELDS:
            v = re.search(rf"\b{ts_key}: ([^,\n]+),", block)
            assert v, f"{ts_key} missing for plan {m.group(1)} in plans.ts"
            raw = v.group(1).strip()
            values[ts_key] = (
                raw == "true"
                if raw in ("true", "false")
                else raw.strip('"')
                if raw.startswith('"')
                else int(raw)
            )
        plans[m.group(1)] = values
    return plans


@pytest.mark.skipif(not PLANS_TS.exists(), reason="frontend not present")
def test_frontend_plans_match_backend() -> None:
    ts = _parse_ts()
    assert set(ts) == {p.value for p in PLANS}
    for plan, limits in PLANS.items():
        for ts_key, py_attr in FIELDS.items():
            assert ts[plan.value][ts_key] == getattr(limits, py_attr), (
                f"{plan.value}.{ts_key} differs"
            )
