"""Marketing Memory: what the business has taught its agent. Retrieved, never trained on."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed
from app.core.errors import AppError, not_found
from app.core.security import utcnow
from app.models import MarketingInsight, MarketingMemory, Workspace
from app.models.enums import InsightStatus, MemoryCategory, MemorySource

MAX_MEMORIES = 500
PROMPT_LIMIT = 8
RELEVANCE_MAX_DISTANCE = 0.9  # cosine distance; beyond this a memory isn't about the topic

INSIGHT_TO_MEMORY = {
    "pillar": MemoryCategory.SUCCESSFUL_TOPIC,
    "format": MemoryCategory.SUCCESSFUL_FORMAT,
    "time": MemoryCategory.POSTING_TIME,
    "platform": MemoryCategory.PLATFORM_PATTERN,
}


def to_out(m: MarketingMemory) -> dict[str, Any]:
    return {
        "id": m.id,
        "category": m.category,
        "source": m.source,
        "content": m.content,
        "pinned": m.pinned,
        "evidence": m.evidence or {},
        "last_used_at": m.last_used_at,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
    }


async def list_memories(
    db: AsyncSession, ws: Workspace, *, q: str | None = None, category: MemoryCategory | None = None
) -> list[MarketingMemory]:
    conds = [MarketingMemory.workspace_id == ws.id, MarketingMemory.deleted_at.is_(None)]
    if category:
        conds.append(MarketingMemory.category == category)
    stmt = select(MarketingMemory).where(*conds)
    if q and q.strip():
        [vec] = await embed([q.strip()])
        dist = MarketingMemory.embedding.cosine_distance(vec)
        stmt = stmt.where(
            or_(dist < RELEVANCE_MAX_DISTANCE, MarketingMemory.content.ilike(f"%{q.strip()}%"))
        ).order_by(dist)
    else:
        stmt = stmt.order_by(MarketingMemory.pinned.desc(), MarketingMemory.updated_at.desc())
    return list((await db.execute(stmt.limit(200))).scalars())


async def create(
    db: AsyncSession,
    ws: Workspace,
    *,
    content: str,
    category: MemoryCategory,
    source: MemorySource = MemorySource.USER,
    pinned: bool = False,
    evidence: dict[str, Any] | None = None,
) -> MarketingMemory:
    count = len(
        (
            await db.execute(
                select(MarketingMemory.id).where(
                    MarketingMemory.workspace_id == ws.id, MarketingMemory.deleted_at.is_(None)
                )
            )
        ).all()
    )
    if count >= MAX_MEMORIES:
        raise AppError(
            409,
            "memory_full",
            f"A business can keep up to {MAX_MEMORIES} memories. Remove some you no longer need.",
        )
    [vec] = await embed([content])
    m = MarketingMemory(
        workspace_id=ws.id,
        category=category,
        source=source,
        content=content.strip(),
        pinned=pinned,
        evidence=evidence or {},
        embedding=vec,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


async def _get(db: AsyncSession, ws: Workspace, memory_id: uuid.UUID) -> MarketingMemory:
    m = await db.get(MarketingMemory, memory_id)
    if m is None or m.workspace_id != ws.id or m.deleted_at is not None:
        raise not_found("Memory")
    return m


async def update(
    db: AsyncSession,
    ws: Workspace,
    memory_id: uuid.UUID,
    *,
    content: str | None,
    category: MemoryCategory | None,
    pinned: bool | None,
) -> MarketingMemory:
    m = await _get(db, ws, memory_id)
    if content is not None and content.strip() != m.content:
        m.content = content.strip()
        [m.embedding] = await embed([m.content])
        if m.source is not MemorySource.USER:
            m.evidence = {**(m.evidence or {}), "edited_by_user": True}
    if category is not None:
        m.category = category
    if pinned is not None:
        m.pinned = pinned
    await db.commit()
    await db.refresh(m)
    return m


async def delete(db: AsyncSession, ws: Workspace, memory_id: uuid.UUID) -> None:
    m = await _get(db, ws, memory_id)
    m.deleted_at = utcnow()
    await db.commit()


async def save_insight(db: AsyncSession, ws: Workspace, insight_id: uuid.UUID) -> MarketingMemory:
    insight = await db.get(MarketingInsight, insight_id)
    if insight is None or insight.workspace_id != ws.id:
        raise not_found("Insight")
    if (insight.evidence or {}).get("memory_id"):
        existing = await db.get(MarketingMemory, uuid.UUID(insight.evidence["memory_id"]))
        if existing and existing.deleted_at is None:
            return existing
    dimension = (insight.evidence or {}).get("dimension", "pillar")
    m = await create(
        db,
        ws,
        content=insight.statement,
        category=INSIGHT_TO_MEMORY.get(dimension, MemoryCategory.PLATFORM_PATTERN),
        source=MemorySource.ANALYTICS,
        evidence={
            "insight_id": str(insight.id),
            "sample_size": insight.sample_size,
            "period": [insight.period_start.isoformat(), insight.period_end.isoformat()],
        },
    )
    insight.evidence = {**(insight.evidence or {}), "memory_id": str(m.id)}
    await db.commit()
    await db.refresh(m)
    return m


async def dismiss_insight(
    db: AsyncSession, ws: Workspace, insight_id: uuid.UUID
) -> MarketingInsight:
    insight = await db.get(MarketingInsight, insight_id)
    if insight is None or insight.workspace_id != ws.id:
        raise not_found("Insight")
    insight.status = InsightStatus.DISMISSED
    await db.commit()
    await db.refresh(insight)
    return insight


async def for_prompt(db: AsyncSession, ws_id: uuid.UUID, topic: str) -> list[MarketingMemory]:
    """Pinned memories plus the most relevant others for this brief (used by the AI writer)."""
    base = [MarketingMemory.workspace_id == ws_id, MarketingMemory.deleted_at.is_(None)]
    pinned = list(
        (
            await db.execute(
                select(MarketingMemory)
                .where(*base, MarketingMemory.pinned.is_(True))
                .limit(PROMPT_LIMIT)
            )
        ).scalars()
    )
    room = PROMPT_LIMIT - len(pinned)
    related: list[MarketingMemory] = []
    if room > 0:
        [vec] = await embed([topic or "content that works for this business"])
        dist = MarketingMemory.embedding.cosine_distance(vec)
        related = list(
            (
                await db.execute(
                    select(MarketingMemory)
                    .where(
                        *base,
                        MarketingMemory.pinned.is_(False),
                        MarketingMemory.embedding.is_not(None),
                    )
                    .order_by(dist)
                    .limit(room)
                )
            ).scalars()
        )
    chosen = pinned + related
    for m in chosen:
        m.last_used_at = utcnow()
    return chosen
