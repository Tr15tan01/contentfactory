"""Provider-neutral AI interface. Callers name a *role*; configuration maps roles to models."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["fast", "reasoning"]


@dataclass(frozen=True)
class CompletionRequest:
    role: Role
    system: str
    prompt: str
    max_tokens: int = 2000
    temperature: float = 0.7
    # Structured context the mock provider can read directly (real providers ignore it:
    # everything they need is in `system` and `prompt`).
    hints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class AIProviderError(Exception):
    """A provider call failed. `retryable` distinguishes outages from bad requests."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class AIProvider(Protocol):
    name: str

    def model_for(self, role: Role) -> str: ...

    async def complete(self, req: CompletionRequest) -> Completion: ...


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


def parse_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a model response (tolerates fences and preamble)."""
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("The AI response didn't contain JSON.")
    data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("The AI response wasn't a JSON object.")
    return data
