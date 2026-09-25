"""Text embeddings for Marketing Memory retrieval.

`local` is a real (if simple) embedding: signed feature hashing of word unigrams and bigrams,
L2-normalised, so cosine similarity reflects shared vocabulary. It needs no API and suits short
business facts. `voyage` (Voyage AI) and `gemini` (Gemini API) are semantic embeddings.
Changing provider requires re-embedding existing memories (`python -m scripts.reembed_memory`).
"""

from __future__ import annotations

import hashlib
import math
import re

import httpx

from app.core.config import settings

_WORD = re.compile(r"[\w']+", re.UNICODE)
_STOP = frozenset(
    "a an and are as at be by for from has have in is it its of on or our that the this to "
    "was we were with you your".split()
)


def _local(text: str, dims: int) -> list[float]:
    words = [w for w in _WORD.findall(text.lower()) if w not in _STOP]
    features = words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)]
    vec = [0.0] * dims
    for f in features:
        h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
        vec[h % dims] += 1.0 if (h >> 63) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


async def embed(texts: list[str], client: httpx.AsyncClient | None = None) -> list[list[float]]:
    dims = settings.AI_EMBEDDING_DIMENSIONS
    if settings.AI_EMBEDDING_PROVIDER == "local":
        return [_local(t, dims) for t in texts]
    if settings.AI_EMBEDDING_PROVIDER == "gemini":
        from app.ai.gemini import embed as gemini_embed

        return await gemini_embed(texts, client)
    async with client or httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.AI_EMBEDDING_API_KEY}"},
            json={"input": texts, "model": settings.AI_EMBEDDING_MODEL, "output_dimension": dims},
        )
        r.raise_for_status()
        return [row["embedding"] for row in sorted(r.json()["data"], key=lambda d: d["index"])]
