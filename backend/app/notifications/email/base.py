from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str


class EmailProvider(Protocol):
    name: str

    async def send(self, message: EmailMessage) -> None: ...
