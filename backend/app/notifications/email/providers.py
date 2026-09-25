from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.notifications.email.base import EmailMessage, EmailProvider

log = logging.getLogger("contentfactory.email")


class ConsoleEmailProvider:
    """Development provider: prints the email (including links) to the worker log."""

    name = "console"

    async def send(self, message: EmailMessage) -> None:
        log.warning(
            "\n--- email to %s ---\n%s\n\n%s\n---", message.to, message.subject, message.text
        )


class ResendEmailProvider:
    name = "resend"
    endpoint = "https://api.resend.com/emails"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def send(self, message: EmailMessage) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": settings.EMAIL_FROM,
                    "to": [message.to],
                    "subject": message.subject,
                    "text": message.text,
                    "html": message.html,
                },
            )
            resp.raise_for_status()


def get_email_provider() -> EmailProvider:
    if settings.EMAIL_PROVIDER == "resend":
        if not settings.EMAIL_PROVIDER_API_KEY:
            raise RuntimeError("EMAIL_PROVIDER=resend requires EMAIL_PROVIDER_API_KEY")
        return ResendEmailProvider(settings.EMAIL_PROVIDER_API_KEY)
    return ConsoleEmailProvider()
