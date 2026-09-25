from __future__ import annotations

import httpx

from app.ai.base import AIProviderError, Completion, CompletionRequest, Role
from app.core.config import settings


class AnthropicProvider:
    """Anthropic Messages API over HTTP (no SDK dependency, so the transport is testable)."""

    name = "anthropic"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=settings.AI_API_BASE_URL, timeout=settings.AI_TIMEOUT_SECONDS
        )

    def model_for(self, role: Role) -> str:
        return settings.AI_REASONING_MODEL if role == "reasoning" else settings.AI_FAST_MODEL

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
        try:
            r = await self._client.post(
                "/v1/messages",
                headers={
                    "x-api-key": settings.AI_PROVIDER_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": req.max_tokens,
                    "temperature": req.temperature,
                    "system": req.system,
                    "messages": [{"role": "user", "content": req.prompt}],
                },
            )
        except httpx.HTTPError as exc:
            raise AIProviderError("The AI service couldn't be reached.", retryable=True) from exc
        if r.status_code in (429, 500, 502, 503, 504, 529):
            raise AIProviderError("The AI service is busy. Try again shortly.", retryable=True)
        if r.status_code >= 400:
            raise AIProviderError(
                f"The AI service rejected the request ({r.status_code}).", retryable=False
            )
        data = r.json()
        text = "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
        usage = data.get("usage", {})
        tin, tout = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
        return Completion(
            text=text,
            provider=self.name,
            model=data.get("model", model),
            input_tokens=tin,
            output_tokens=tout,
            cost_usd=self._cost(req.role, tin, tout),
        )
