from __future__ import annotations

from app.ai.base import AIProvider
from app.core.config import settings

_provider: AIProvider | None = None


def get_provider() -> AIProvider:
    global _provider
    if _provider is None:
        if settings.AI_PROVIDER == "anthropic":
            from app.ai.anthropic import AnthropicProvider

            _provider = AnthropicProvider()
        elif settings.AI_PROVIDER == "gemini":
            from app.ai.gemini import GeminiProvider

            _provider = GeminiProvider()
        else:
            from app.ai.mock import MockProvider

            _provider = MockProvider()
    return _provider


def set_provider(provider: AIProvider | None) -> None:
    """Swap the provider (tests)."""
    global _provider
    _provider = provider
