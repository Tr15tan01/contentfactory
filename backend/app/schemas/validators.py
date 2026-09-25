from __future__ import annotations

from functools import lru_cache
from zoneinfo import available_timezones


@lru_cache(maxsize=1)
def _zones() -> frozenset[str]:
    return frozenset(available_timezones())


def iana_timezone(value: str | None) -> str | None:
    """Accept only real IANA zone names; schedules and reports are computed in them."""
    if value is None:
        return None
    value = value.strip()
    if value not in _zones():
        raise ValueError("Choose a time zone from the list, for example Europe/London.")
    return value
