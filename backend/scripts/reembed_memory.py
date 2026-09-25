"""Recompute every Marketing Memory embedding with the current AI_EMBEDDING_PROVIDER.

Run this after changing AI_EMBEDDING_PROVIDER or AI_EMBEDDING_MODEL: vectors from different
models aren't comparable, so memory retrieval is wrong until everything is re-embedded.
AI_EMBEDDING_DIMENSIONS must stay the same (it's the database column size).

python -m scripts.reembed_memory
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.ai.embeddings import embed
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import MarketingMemory

BATCH = 50


async def main() -> None:
    async with SessionLocal() as db:
        total = await db.scalar(select(func.count()).select_from(MarketingMemory)) or 0
        print(f"Re-embedding {total} memories with {settings.AI_EMBEDDING_PROVIDER}...")
        done, last_id = 0, None
        while True:
            q = select(MarketingMemory).order_by(MarketingMemory.id).limit(BATCH)
            if last_id is not None:
                q = q.where(MarketingMemory.id > last_id)
            rows = list((await db.scalars(q)).all())
            if not rows:
                break
            vectors = await embed([m.content for m in rows])
            for m, vec in zip(rows, vectors, strict=True):
                m.embedding = vec
            await db.commit()
            done += len(rows)
            last_id = rows[-1].id
            print(f"  {done}/{total}")
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
