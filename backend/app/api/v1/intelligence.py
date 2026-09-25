from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select

from app.analytics import insights as insights_engine
from app.analytics import service as analytics
from app.auth.dependencies import DB, CurrentWorkspace
from app.core.rate_limit import rate_limit
from app.intelligence import experiments, memory
from app.models import MarketingInsight
from app.models.enums import InsightStatus, MemoryCategory, WorkspaceRole
from app.schemas.intelligence import (
    AnalyticsOut,
    AssignIn,
    ExperimentIn,
    ExperimentOut,
    InsightOut,
    MemoryIn,
    MemoryOut,
    MemoryUpdate,
)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["intelligence"])
EDITORS = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR)


@router.get("/analytics", response_model=AnalyticsOut)
async def get_analytics(
    ctx: CurrentWorkspace, db: DB, days: Annotated[int, Query(ge=7, le=90)] = 30
) -> AnalyticsOut:
    return AnalyticsOut.model_validate(await analytics.overview(db, ctx.workspace, days))


@router.get("/insights", response_model=list[InsightOut])
async def list_insights(
    ctx: CurrentWorkspace, db: DB, include_dismissed: bool = False
) -> list[InsightOut]:
    statuses = [InsightStatus.ACTIVE] + (
        [InsightStatus.DISMISSED, InsightStatus.SUPERSEDED] if include_dismissed else []
    )
    rows = await db.execute(
        select(MarketingInsight)
        .where(
            MarketingInsight.workspace_id == ctx.workspace.id, MarketingInsight.status.in_(statuses)
        )
        .order_by(MarketingInsight.updated_at.desc())
    )
    return [InsightOut.model_validate(i, from_attributes=True) for i in rows.scalars()]


@router.post("/insights/refresh", dependencies=[Depends(rate_limit("insights_refresh", 6, 60))])
async def refresh_insights(ctx: CurrentWorkspace, db: DB) -> dict[str, int]:
    ctx.require_role(*EDITORS)
    return await insights_engine.analyze(db, ctx.workspace)


@router.post("/insights/{insight_id}/remember", response_model=MemoryOut)
async def remember(insight_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> MemoryOut:
    ctx.require_role(*EDITORS)
    return MemoryOut.model_validate(
        memory.to_out(await memory.save_insight(db, ctx.workspace, insight_id))
    )


@router.post("/insights/{insight_id}/dismiss", response_model=InsightOut)
async def dismiss(insight_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> InsightOut:
    ctx.require_role(*EDITORS)
    return InsightOut.model_validate(
        await memory.dismiss_insight(db, ctx.workspace, insight_id), from_attributes=True
    )


@router.get("/memory", response_model=list[MemoryOut])
async def list_memory(
    ctx: CurrentWorkspace,
    db: DB,
    q: Annotated[str | None, Query(max_length=200)] = None,
    category: MemoryCategory | None = None,
) -> list[MemoryOut]:
    return [
        MemoryOut.model_validate(memory.to_out(m))
        for m in await memory.list_memories(db, ctx.workspace, q=q, category=category)
    ]


@router.post("/memory", response_model=MemoryOut, status_code=201)
async def add_memory(body: MemoryIn, ctx: CurrentWorkspace, db: DB) -> MemoryOut:
    ctx.require_role(*EDITORS)
    return MemoryOut.model_validate(
        memory.to_out(
            await memory.create(
                db, ctx.workspace, content=body.content, category=body.category, pinned=body.pinned
            )
        )
    )


@router.patch("/memory/{memory_id}", response_model=MemoryOut)
async def edit_memory(
    memory_id: uuid.UUID, body: MemoryUpdate, ctx: CurrentWorkspace, db: DB
) -> MemoryOut:
    ctx.require_role(*EDITORS)
    m = await memory.update(
        db,
        ctx.workspace,
        memory_id,
        content=body.content,
        category=body.category,
        pinned=body.pinned,
    )
    return MemoryOut.model_validate(memory.to_out(m))


@router.delete("/memory/{memory_id}", status_code=204)
async def delete_memory(memory_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> Response:
    ctx.require_role(*EDITORS)
    await memory.delete(db, ctx.workspace, memory_id)
    return Response(status_code=204)


@router.get("/experiments", response_model=list[ExperimentOut])
async def list_experiments(ctx: CurrentWorkspace, db: DB) -> list[ExperimentOut]:
    from app.models import Experiment

    rows = (
        await db.execute(
            select(Experiment)
            .where(Experiment.workspace_id == ctx.workspace.id)
            .order_by(Experiment.created_at.desc())
        )
    ).scalars()
    return [ExperimentOut.model_validate(await experiments.to_out(db, e)) for e in rows]


@router.post("/experiments", response_model=ExperimentOut, status_code=201)
async def create_experiment(body: ExperimentIn, ctx: CurrentWorkspace, db: DB) -> ExperimentOut:
    ctx.require_role(*EDITORS)
    e = await experiments.create(
        db,
        ctx.workspace,
        name=body.name,
        hypothesis=body.hypothesis,
        variable=body.variable,
        metric=body.primary_metric,
        a=body.variant_a,
        b=body.variant_b,
        min_sample=body.min_sample_per_variant,
    )
    return ExperimentOut.model_validate(await experiments.to_out(db, e))


@router.put("/experiments/{experiment_id}/variants/{label}", response_model=ExperimentOut)
async def assign(
    experiment_id: uuid.UUID, label: str, body: AssignIn, ctx: CurrentWorkspace, db: DB
) -> ExperimentOut:
    ctx.require_role(*EDITORS)
    e = await experiments.assign(db, ctx.workspace, experiment_id, label.upper(), body.content_ids)
    return ExperimentOut.model_validate(await experiments.to_out(db, e))


@router.post("/experiments/{experiment_id}/evaluate", response_model=ExperimentOut)
async def evaluate(experiment_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> ExperimentOut:
    ctx.require_role(*EDITORS)
    return ExperimentOut.model_validate(
        await experiments.to_out(db, await experiments.evaluate(db, ctx.workspace, experiment_id))
    )


@router.post("/experiments/{experiment_id}/cancel", response_model=ExperimentOut)
async def cancel(experiment_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> ExperimentOut:
    ctx.require_role(*EDITORS)
    return ExperimentOut.model_validate(
        await experiments.to_out(db, await experiments.cancel(db, ctx.workspace, experiment_id))
    )
