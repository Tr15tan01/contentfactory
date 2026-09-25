"""Google Gemini over the REST API (no SDK, so the transport is testable).

One API key (AI_PROVIDER_API_KEY, or the per-feature key if set) covers text, images and
embeddings. Gemini 3.x models ignore temperature and use `thinkingLevel` instead; thinking
tokens count against maxOutputTokens and are billed as output, so we add headroom for them
and include them in the cost.
"""

from __future__ import annotations

import base64
import logging
import math
from typing import Any

import httpx

from app.ai.base import AIProviderError, Completion, CompletionRequest, Role
from app.ai.images import GeneratedImage
from app.core.config import settings

log = logging.getLogger(__name__)

RETRYABLE = (429, 500, 502, 503, 504)
# Extra output budget reserved for thinking, on top of the tokens the caller asked for.
THINKING_HEADROOM = {"": 8192, "minimal": 1024, "low": 4096, "medium": 12288, "high": 24576}
BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "IMAGE_SAFETY", "RECITATION"}
# Our aspect names -> Gemini aspect ratios (closest supported ratio to the SIZES in images.py).
ASPECTS = {"square": "1:1", "portrait": "4:5", "landscape": "5:4", "story": "9:16"}
EMBED_BATCH = 100


def _client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.GEMINI_API_BASE_URL.rstrip("/"), timeout=timeout)


def _error_detail(r: httpx.Response) -> str:
    try:
        return str((r.json().get("error") or {}).get("message", ""))[:300]
    except ValueError:
        return ""


def _raise_for_status(r: httpx.Response, what: str) -> None:
    if r.status_code < 400:
        return
    detail = _error_detail(r)
    log.warning("Gemini %s call failed: %s %s", what, r.status_code, detail)
    if r.status_code in RETRYABLE:
        raise AIProviderError(f"The {what} service is busy. Try again shortly.", retryable=True)
    if r.status_code in (401, 403) or "API key" in detail:
        raise AIProviderError(
            f"The {what} service rejected the API key ({r.status_code}).", retryable=False
        )
    raise AIProviderError(
        f"The {what} service rejected the request ({r.status_code}). {detail}".strip(),
        retryable=False,
    )


def _blocked(data: dict[str, Any]) -> str | None:
    feedback = data.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        return str(feedback["blockReason"])
    for cand in data.get("candidates") or []:
        if cand.get("finishReason") in BLOCKED:
            return str(cand["finishReason"])
    return None


def _parts(data: dict[str, Any]) -> list[dict[str, Any]]:
    cands = data.get("candidates") or []
    return list((cands[0].get("content") or {}).get("parts") or []) if cands else []


class GeminiProvider:
    name = "gemini"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or _client(settings.AI_TIMEOUT_SECONDS)

    def model_for(self, role: Role) -> str:
        return settings.AI_REASONING_MODEL if role == "reasoning" else settings.AI_FAST_MODEL

    def _thinking(self, role: Role) -> str:
        level = (
            settings.AI_REASONING_THINKING_LEVEL
            if role == "reasoning"
            else settings.AI_FAST_THINKING_LEVEL
        )
        return level.strip().lower()

    def _cost(self, role: Role, tin: int, tout: int) -> float:
        if role == "reasoning":
            rin, rout = (
                settings.AI_REASONING_INPUT_USD_PER_MTOK,
                settings.AI_REASONING_OUTPUT_USD_PER_MTOK,
            )
        else:
            rin, rout = settings.AI_FAST_INPUT_USD_PER_MTOK, settings.AI_FAST_OUTPUT_USD_PER_MTOK
        return (tin * rin + tout * rout) / 1_000_000

    async def complete(self, req: CompletionRequest) -> Completion:
        model = self.model_for(req.role)
        level = self._thinking(req.role)
        config: dict[str, Any] = {
            "maxOutputTokens": req.max_tokens + THINKING_HEADROOM.get(level, 8192)
        }
        if level:
            config["thinkingConfig"] = {"thinkingLevel": level}
        try:
            r = await self._client.post(
                f"/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": settings.AI_PROVIDER_API_KEY},
                json={
                    "systemInstruction": {"parts": [{"text": req.system}]},
                    "contents": [{"role": "user", "parts": [{"text": req.prompt}]}],
                    "generationConfig": config,
                },
            )
        except httpx.HTTPError as exc:
            raise AIProviderError("The AI service couldn't be reached.", retryable=True) from exc
        _raise_for_status(r, "AI")
        data = r.json()
        if reason := _blocked(data):
            raise AIProviderError(
                f"The AI service declined to write this ({reason}). Try rewording the brief.",
                retryable=False,
            )
        text = "".join(p.get("text", "") for p in _parts(data) if not p.get("thought"))
        if not text.strip():
            finish = ((data.get("candidates") or [{}])[0]).get("finishReason", "")
            raise AIProviderError(
                f"The AI service returned no text ({finish or 'empty response'}).",
                retryable=finish != "MAX_TOKENS",
            )
        usage = data.get("usageMetadata") or {}
        tin = int(usage.get("promptTokenCount", 0))
        tout = int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
        return Completion(
            text=text,
            provider=self.name,
            model=data.get("modelVersion", model),
            input_tokens=tin,
            output_tokens=tout,
            cost_usd=self._cost(req.role, tin, tout),
        )


class GeminiImageProvider:
    """Native image generation (e.g. gemini-3.1-flash-image) via generateContent."""

    name = "gemini"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or _client(180)

    @property
    def model(self) -> str:
        return settings.AI_IMAGE_MODEL

    async def _post(
        self, version: str, config_key: str, prompt: str, aspect: str
    ) -> httpx.Response:
        image = {"aspectRatio": ASPECTS.get(aspect, "1:1"), "imageSize": "1K"}
        config: dict[str, Any] = {"responseModalities": ["TEXT", "IMAGE"]}
        # Current docs: generationConfig.responseFormat.image; older API versions: imageConfig.
        config[config_key] = {"image": image} if config_key == "responseFormat" else image
        return await self._client.post(
            f"/{version}/models/{self.model}:generateContent",
            headers={"x-goog-api-key": settings.image_api_key},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config},
        )

    async def generate(self, prompt: str, aspect: str) -> GeneratedImage:
        try:
            r = await self._post("v1", "responseFormat", prompt, aspect)
            if r.status_code in (400, 404) and (
                r.status_code == 404 or "responseFormat" in _error_detail(r)
            ):
                r = await self._post("v1beta", "imageConfig", prompt, aspect)
        except httpx.HTTPError as exc:
            raise AIProviderError("The image service couldn't be reached.", retryable=True) from exc
        _raise_for_status(r, "image")
        data = r.json()
        if reason := _blocked(data):
            raise AIProviderError(
                f"The image service refused this prompt ({reason}).", retryable=False
            )
        for part in _parts(data):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                note = " ".join(p["text"] for p in _parts(data) if p.get("text")) or None
                return GeneratedImage(
                    base64.b64decode(inline["data"]), mime, self.name, self.model, note
                )
        raise AIProviderError("The image service returned no image.", retryable=False)


async def embed(texts: list[str], client: httpx.AsyncClient | None = None) -> list[list[float]]:
    """gemini-embedding-001 via batchEmbedContents. Vectors below 3072 dimensions aren't
    normalised by the API, so we L2-normalise them (cosine distance assumes unit length)."""
    model, dims = settings.AI_EMBEDDING_MODEL, settings.AI_EMBEDDING_DIMENSIONS
    out: list[list[float]] = []
    async with client or _client(60) as c:
        for i in range(0, len(texts), EMBED_BATCH):
            chunk = texts[i : i + EMBED_BATCH]
            try:
                r = await c.post(
                    f"/v1beta/models/{model}:batchEmbedContents",
                    headers={"x-goog-api-key": settings.embedding_api_key},
                    json={
                        "requests": [
                            {
                                "model": f"models/{model}",
                                "content": {"parts": [{"text": t}]},
                                "taskType": "SEMANTIC_SIMILARITY",
                                "outputDimensionality": dims,
                            }
                            for t in chunk
                        ]
                    },
                )
            except httpx.HTTPError as exc:
                raise AIProviderError(
                    "The embedding service couldn't be reached.", retryable=True
                ) from exc
            _raise_for_status(r, "embedding")
            for row in r.json().get("embeddings") or []:
                vec = [float(v) for v in row["values"]]
                if len(vec) != dims:
                    raise AIProviderError(
                        f"Embedding size {len(vec)} doesn't match AI_EMBEDDING_DIMENSIONS={dims}.",
                        retryable=False,
                    )
                norm = math.sqrt(sum(v * v for v in vec)) or 1.0
                out.append([v / norm for v in vec])
    if len(out) != len(texts):
        raise AIProviderError("The embedding service returned too few vectors.", retryable=False)
    return out
