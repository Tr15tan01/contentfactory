"""What can be uploaded, how big, and how we recognise it from its bytes (not its name)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.core.config import settings
from app.models.enums import MediaKind


@dataclass(frozen=True)
class MediaType:
    mime: str
    kind: MediaKind
    ext: str


ALLOWED: dict[str, MediaType] = {
    t.mime: t
    for t in (
        MediaType("image/jpeg", MediaKind.IMAGE, "jpg"),
        MediaType("image/png", MediaKind.IMAGE, "png"),
        MediaType("image/webp", MediaKind.IMAGE, "webp"),
        MediaType("image/gif", MediaKind.IMAGE, "gif"),
        MediaType("video/mp4", MediaKind.VIDEO, "mp4"),
        MediaType("video/quicktime", MediaKind.VIDEO, "mov"),
        MediaType("video/webm", MediaKind.VIDEO, "webm"),
    )
}


def max_bytes(kind: MediaKind) -> int:
    mb = settings.MEDIA_MAX_VIDEO_MB if kind is MediaKind.VIDEO else settings.MEDIA_MAX_IMAGE_MB
    return mb * 1024 * 1024


def sniff(head: bytes) -> str | None:
    """Detect the real type from magic bytes. SVG and HTML are deliberately unsupported."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        return "video/quicktime" if brand == b"qt  " else "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    return None


def compatible(declared: str, detected: str | None) -> bool:
    if detected is None:
        return False
    if declared == detected:
        return True
    # Phones label MOV/MP4 inconsistently; both are ISO-BMFF containers.
    return {declared, detected} <= {"video/mp4", "video/quicktime"}


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str, ext: str) -> str:
    stem = unicodedata.normalize("NFKD", name.rsplit(".", 1)[0]).encode("ascii", "ignore").decode()
    stem = _UNSAFE.sub("-", stem).strip("-._")[:80] or "file"
    return f"{stem.lower()}.{ext}"


def display_name(name: str) -> str:
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return (stem.strip() or "Untitled")[:255]


def normalize_tags(tags: list[str]) -> list[str]:
    seen: list[str] = []
    for tag in tags:
        t = " ".join(tag.lower().strip().lstrip("#").split())[:64]
        if t and t not in seen:
            seen.append(t)
    return seen[:30]
