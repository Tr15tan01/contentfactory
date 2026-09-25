"""Image generation providers. Callers get PNG/JPEG bytes; storage and accounting live elsewhere."""

from __future__ import annotations

import base64
import hashlib
import io
import textwrap
from dataclasses import dataclass
from typing import Protocol

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.ai.base import AIProviderError
from app.core.config import settings

SIZES = {
    "square": (1024, 1024),
    "portrait": (1024, 1280),
    "landscape": (1280, 1024),
    "story": (1024, 1792),
}
OPENAI_SIZES = {
    "square": "1024x1024",
    "portrait": "1024x1536",
    "landscape": "1536x1024",
    "story": "1024x1536",
}


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    mime_type: str
    provider: str
    model: str
    revised_prompt: str | None = None


class ImageProvider(Protocol):
    name: str

    @property
    def model(self) -> str: ...

    async def generate(self, prompt: str, aspect: str) -> GeneratedImage: ...


class MockImageProvider:
    """Development placeholder: a clearly labelled card with the prompt, drawn locally.
    Refused in production. It exists so the whole flow (quota, storage, reuse) runs offline."""

    name = "mock"

    @property
    def model(self) -> str:
        return "placeholder-v1"

    async def generate(self, prompt: str, aspect: str) -> GeneratedImage:
        w, h = SIZES.get(aspect, SIZES["square"])
        seed = hashlib.sha256(prompt.encode()).digest()
        top = (40 + seed[0] // 3, 70 + seed[1] // 4, 70 + seed[2] // 4)
        bottom = (15 + seed[3] // 6, 30 + seed[4] // 6, 35 + seed[5] // 6)
        im = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(im)
        for y in range(h):
            t = y / h
            draw.line(
                [(0, y), (w, y)],
                fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
            )
        try:
            big = ImageFont.truetype(settings.video_font_path or "", 44)
            small = ImageFont.truetype(settings.video_font_path or "", 30)
        except OSError:
            big = small = ImageFont.load_default()
        draw.rectangle([0, 0, w, 90], fill=(245, 213, 71))
        draw.text((36, 24), "DEVELOPMENT PLACEHOLDER, NOT AI", font=big, fill=(16, 35, 38))
        y = 150
        for line in textwrap.wrap(prompt, 48)[:14]:
            draw.text((48, y), line, font=small, fill=(230, 238, 236))
            y += 44
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        return GeneratedImage(buf.getvalue(), "image/png", self.name, self.model)


class OpenAIImageProvider:
    """OpenAI-compatible `POST /images/generations` returning base64 (b64_json)."""

    name = "openai"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=settings.AI_IMAGE_API_BASE_URL.rstrip("/"), timeout=180
        )

    @property
    def model(self) -> str:
        return settings.AI_IMAGE_MODEL

    async def generate(self, prompt: str, aspect: str) -> GeneratedImage:
        try:
            r = await self._client.post(
                "/images/generations",
                headers={"Authorization": f"Bearer {settings.AI_IMAGE_API_KEY}"},
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "size": OPENAI_SIZES.get(aspect, "1024x1024"),
                    "n": 1,
                },
            )
        except httpx.HTTPError as exc:
            raise AIProviderError("The image service couldn't be reached.", retryable=True) from exc
        if r.status_code == 400:
            detail = (r.json().get("error") or {}).get("message", "") if r.content else ""
            raise AIProviderError(
                f"The image service refused this prompt. {detail}".strip(), retryable=False
            )
        if r.status_code in (429, 500, 502, 503, 504):
            raise AIProviderError("The image service is busy. Try again shortly.", retryable=True)
        if r.status_code >= 400:
            raise AIProviderError(
                f"The image service returned an error ({r.status_code}).", retryable=False
            )
        item = (r.json().get("data") or [{}])[0]
        if not item.get("b64_json"):
            raise AIProviderError("The image service returned no image.", retryable=False)
        data = base64.b64decode(item["b64_json"])
        mime = "image/jpeg" if data[:3] == b"\xff\xd8\xff" else "image/png"
        return GeneratedImage(data, mime, self.name, self.model, item.get("revised_prompt"))


_provider: ImageProvider | None = None


def get_image_provider() -> ImageProvider:
    global _provider
    if _provider is None:
        if settings.AI_IMAGE_PROVIDER == "openai":
            _provider = OpenAIImageProvider()
        elif settings.AI_IMAGE_PROVIDER == "gemini":
            from app.ai.gemini import GeminiImageProvider

            _provider = GeminiImageProvider()
        else:
            _provider = MockImageProvider()
    return _provider


def set_image_provider(provider: ImageProvider | None) -> None:
    global _provider
    _provider = provider
