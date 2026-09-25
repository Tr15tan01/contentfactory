"""Simple A/B experiments: posts are assigned to variant A or B; results come from real metrics."""

from __future__ import annotations

import uuid
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.collector import engagements
from app.billing.entitlements import plan_required, workspace_plan
from app.core.errors import AppError, not_found
from app.core.security import utcnow
from app.intelligence import memory
from app.models import (
    Content,
    Experiment,
    ExperimentVariant,
    PlatformMetric,
    Publication,
    Workspace,
)
from app.models.enums import (
    Confidence,
    ExperimentStatus,
    MemoryCategory,
    MemorySource,
    PublicationStatus,
)

RUNNING_LIMIT = {"none": 0, "basic": 1, "full": 3, "advanced": 10}
MIN_LIFT = 0.15
VARIABLES = ("hook", "cta", "format", "time", "topic", "visual")
METRICS = ("engagements", "saves", "reach", "views", "shares", "comments", "likes")


async def to_out(db: AsyncSession, e: Experiment) -> dict[str, Any]:
    variants = (
        (
            await db.execute(
                select(ExperimentVariant)
                .where(ExperimentVariant.experiment_id == e.id)
                .order_by(ExperimentVariant.label)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": e.id,
        "name": e.name,
        "hypothesis": e.hypothesis,
        "variable": e.variable,
        "primary_metric": e.primary_metric,
        "status": e.status,
        "min_sample_per_variant": e.min_sample_per_variant,
        "confidence": e.confidence,
        "conclusion": e.conclusion,
        "result": e.result or {},
        "winner_variant_id": e.winner_variant_id,
        "created_at": e.created_at,
        "variants": [
            {
                "id": v.id,
                "label": v.label,
                "description": v.description,
                "content_ids": v.config.get("content_ids", []),
                "sample_size": v.sample_size,
                "metrics": v.metrics or {},
            }
            for v in variants
        ],
    }


async def create(
    db: AsyncSession,
    ws: Workspace,
    *,
    name: str,
    hypothesis: str,
    variable: str,
    metric: str,
    a: str,
    b: str,
    min_sample: int,
) -> Experiment:
    plan = await workspace_plan(db, ws)
    limit = RUNNING_LIMIT[plan.experiments]
    if limit == 0:
        raise plan_required("Experiments", "Starter")
    running = (
        await db.execute(
            select(func.count())
            .select_from(Experiment)
            .where(Experiment.workspace_id == ws.id, Experiment.status == ExperimentStatus.RUNNING)
        )
    ).scalar_one()
    if running >= limit:
        raise AppError(
            409,
            "experiment_limit",
            f"Your plan runs up to {limit} experiment{'s' if limit != 1 else ''} at a time. "
            "Finish or cancel one first.",
        )
    if variable not in VARIABLES or metric not in METRICS:
        raise AppError(422, "invalid_experiment", "Unknown variable or metric.")
    e = Experiment(
        workspace_id=ws.id,
        name=name.strip(),
        hypothesis=hypothesis.strip(),
        variable=variable,
        primary_metric=metric,
        status=ExperimentStatus.RUNNING,
        confidence=Confidence.NONE,
        min_sample_per_variant=min_sample,
        start_date=utcnow().date(),
    )
    db.add(e)
    await db.flush()
    for label, desc in (("A", a), ("B", b)):
        db.add(
            ExperimentVariant(
                experiment_id=e.id,
                label=label,
                description=desc.strip(),
                config={"content_ids": []},
            )
        )
    await db.commit()
    return e


async def get(db: AsyncSession, ws: Workspace, experiment_id: uuid.UUID) -> Experiment:
    e = await db.get(Experiment, experiment_id)
    if e is None or e.workspace_id != ws.id:
        raise not_found("Experiment")
    return e


async def assign(
    db: AsyncSession,
    ws: Workspace,
    experiment_id: uuid.UUID,
    label: str,
    content_ids: list[uuid.UUID],
) -> Experiment:
    e = await get(db, ws, experiment_id)
    if e.status is not ExperimentStatus.RUNNING:
        raise AppError(409, "not_running", "Only running experiments can change.")
    found = set(
        (
            await db.execute(
                select(Content.id).where(
                    Content.id.in_(content_ids or [uuid.uuid4()]),
                    Content.workspace_id == ws.id,
                    Content.deleted_at.is_(None),
                )
            )
        ).scalars()
    )
    if len(found) != len(set(content_ids)):
        raise not_found("Post")
    variants = {
        v.label: v
        for v in (
            await db.execute(
                select(ExperimentVariant).where(ExperimentVariant.experiment_id == e.id)
            )
        ).scalars()
    }
    if label not in variants:
        raise not_found("Variant")
    other = next(v for k, v in variants.items() if k != label)
    if set(map(str, content_ids)) & set(other.config.get("content_ids", [])):
        raise AppError(422, "in_both_variants", "A post can only be in one variant.")
    variants[label].config = {
        **variants[label].config,
        "content_ids": [str(c) for c in dict.fromkeys(content_ids)],
    }
    await db.commit()
    return e


def _value(m: PlatformMetric, metric: str) -> float | None:
    if metric == "engagements":
        return engagements(m)
    v = getattr(m, metric)
    return float(v) if v is not None else None


async def evaluate(db: AsyncSession, ws: Workspace, experiment_id: uuid.UUID) -> Experiment:
    e = await get(db, ws, experiment_id)
    if e.status is not ExperimentStatus.RUNNING:
        return e
    variants = list(
        (
            await db.execute(
                select(ExperimentVariant)
                .where(ExperimentVariant.experiment_id == e.id)
                .order_by(ExperimentVariant.label)
            )
        ).scalars()
    )
    for v in variants:
        ids = [uuid.UUID(c) for c in v.config.get("content_ids", [])]
        rows = (
            (
                await db.execute(
                    select(PlatformMetric)
                    .join(Publication, Publication.id == PlatformMetric.publication_id)
                    .where(
                        Publication.content_id.in_(ids or [uuid.uuid4()]),
                        Publication.status == PublicationStatus.PUBLISHED,
                    )
                )
            )
            .scalars()
            .all()
        )
        values = [x for x in (_value(m, e.primary_metric) for m in rows) if x is not None]
        v.sample_size = len(values)
        v.metrics = {"mean": round(mean(values), 2) if values else None, "posts_assigned": len(ids)}
    a, b = variants
    enough = min(a.sample_size, b.sample_size) >= e.min_sample_per_variant
    result: dict[str, Any] = {"evaluated_at": utcnow().isoformat(), "enough_data": enough}
    if enough and a.metrics["mean"] is not None and b.metrics["mean"] is not None:
        hi, lo = (a, b) if a.metrics["mean"] >= b.metrics["mean"] else (b, a)
        lift = (
            (hi.metrics["mean"] - lo.metrics["mean"]) / lo.metrics["mean"]
            if lo.metrics["mean"]
            else None
        )
        result["lift"] = round(lift, 4) if lift is not None else None
        e.end_date = utcnow().date()
        if lift is not None and lift >= MIN_LIFT:
            e.status, e.winner_variant_id = ExperimentStatus.COMPLETED, hi.id
            e.confidence = (
                Confidence.HIGH
                if min(a.sample_size, b.sample_size) >= 3 * e.min_sample_per_variant
                else Confidence.MEDIUM
            )
            e.conclusion = (
                f"{hi.label} ({hi.description}) beat {lo.label} ({lo.description}) "
                f"on {e.primary_metric}: "
                f"{hi.metrics['mean']:,.0f} vs {lo.metrics['mean']:,.0f} per post ({lift:+.0%}), "
                f"{a.sample_size + b.sample_size} posts."
            )
            await memory.create(
                db,
                ws,
                content=f"Experiment \u201c{e.name}\u201d: {e.conclusion}",
                category=MemoryCategory.EXPERIMENT,
                source=MemorySource.EXPERIMENT,
                evidence={"experiment_id": str(e.id)},
            )
        else:
            e.status, e.confidence = ExperimentStatus.INCONCLUSIVE, Confidence.LOW
            e.conclusion = f"No clear winner: the difference was under {MIN_LIFT:.0%}."
    e.result = result
    await db.commit()
    return e


async def cancel(db: AsyncSession, ws: Workspace, experiment_id: uuid.UUID) -> Experiment:
    e = await get(db, ws, experiment_id)
    if e.status is ExperimentStatus.RUNNING:
        e.status, e.end_date = ExperimentStatus.CANCELLED, utcnow().date()
        await db.commit()
    return e
