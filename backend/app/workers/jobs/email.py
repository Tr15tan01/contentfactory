from __future__ import annotations

from typing import Any

from app.notifications.email.providers import get_email_provider
from app.notifications.email.templates import render


async def send_email(ctx: dict[str, Any], template: str, to: str, params: dict[str, Any]) -> None:
    message = render(template, to, params)
    await get_email_provider().send(message)
