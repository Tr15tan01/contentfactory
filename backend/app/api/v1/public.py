from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app.auth.dependencies import Queue
from app.core.config import settings
from app.core.rate_limit import rate_limit

router = APIRouter(prefix="/public", tags=["public"])


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    topic: Literal["sales", "support", "partnership", "press", "other"]
    message: str = Field(min_length=10, max_length=5000)


@router.post("/contact", status_code=202, dependencies=[Depends(rate_limit("contact", 5, 3600))])
async def contact(body: ContactIn, queue: Queue) -> dict[str, str]:
    await queue.enqueue(
        "send_email",
        template="contact_form",
        to=settings.SUPPORT_EMAIL,
        params={
            "from_name": body.name,
            "from_email": body.email,
            "topic": body.topic,
            "message": body.message,
        },
    )
    return {"status": "Thanks — we'll reply within one business day."}
