"""Agent activity log: every piece of agent work leaves a run with plain-language steps."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models import AgentRun, AgentStep
from app.models.enums import AgentKind, AgentRunStatus, AgentTrigger

LIMITS = {"max_steps": 20, "max_runtime_seconds": 900, "max_cost_usd": Decimal("1.00")}


async def start(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    agent: AgentKind,
    goal: str,
    *,
    trigger: AgentTrigger = AgentTrigger.SYSTEM,
    user_id: uuid.UUID | None = None,
    data: dict[str, Any] | None = None,
) -> AgentRun:
    run = AgentRun(
        workspace_id=workspace_id,
        agent=agent,
        trigger=trigger,
        triggered_by_id=user_id,
        status=AgentRunStatus.RUNNING,
        goal=goal[:300],
        input=data or {},
        started_at=utcnow(),
        **LIMITS,
    )
    db.add(run)
    await db.flush()
    return run


async def step(
    db: AsyncSession,
    run: AgentRun,
    title: str,
    *,
    detail: str | None = None,
    kind: str = "result",
    status: AgentRunStatus = AgentRunStatus.SUCCEEDED,
    cost: float = 0,
    data: dict[str, Any] | None = None,
) -> None:
    position = run.steps_taken or 0  # in-memory counter: unflushed steps are counted too
    now = utcnow()
    db.add(
        AgentStep(
            run_id=run.id,
            position=position,
            kind=kind,
            title=title[:300],
            detail=detail,
            status=status,
            data=data or {},
            cost_usd=Decimal(str(round(cost, 6))),
            started_at=now,
            finished_at=now,
        )
    )
    run.steps_taken = position + 1
    run.cost_usd = (run.cost_usd or Decimal(0)) + Decimal(str(round(cost, 6)))


def finish(
    run: AgentRun, status: AgentRunStatus, summary: str, *, error: str | None = None
) -> None:
    run.status, run.summary, run.error, run.finished_at = status, summary[:2000], error, utcnow()
