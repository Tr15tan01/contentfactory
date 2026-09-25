from __future__ import annotations

from app.models.enums import Platform
from app.social.base import SocialAdapter

_adapters: dict[str, SocialAdapter] = {}


def _defaults() -> dict[str, SocialAdapter]:
    from app.social.adapters.meta import MetaAdapter
    from app.social.adapters.tiktok import TikTokAdapter
    from app.social.adapters.youtube import YouTubeAdapter

    return {"meta": MetaAdapter(), "tiktok": TikTokAdapter(), "youtube": YouTubeAdapter()}


def adapters() -> dict[str, SocialAdapter]:
    if not _adapters:
        _adapters.update(_defaults())
    return _adapters


def adapter(provider: str) -> SocialAdapter | None:
    return adapters().get(provider)


def for_platform(platform: Platform) -> SocialAdapter | None:
    return next((a for a in adapters().values() if platform in a.platforms), None)


def set_adapters(custom: dict[str, SocialAdapter] | None) -> None:
    """Swap adapters (tests inject ones with mocked HTTP transports)."""
    _adapters.clear()
    if custom:
        _adapters.update(custom)
