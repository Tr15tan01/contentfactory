"""Platform format rules and brand-safety checks applied to every draft (AI or human)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import ContentStatus, ContentType, Platform


@dataclass(frozen=True)
class PlatformRules:
    caption_max: int
    hashtags_max: int
    types: tuple[ContentType, ...]
    needs_video: tuple[ContentType, ...] = ()


RULES: dict[Platform, PlatformRules] = {
    Platform.INSTAGRAM: PlatformRules(
        2200,
        30,
        (ContentType.POST, ContentType.CAROUSEL, ContentType.REEL, ContentType.STORY),
        (ContentType.REEL,),
    ),
    Platform.FACEBOOK: PlatformRules(
        5000,
        10,
        (
            ContentType.POST,
            ContentType.CAROUSEL,
            ContentType.REEL,
            ContentType.STORY,
            ContentType.VIDEO,
        ),
        (ContentType.REEL, ContentType.VIDEO),
    ),
    Platform.TIKTOK: PlatformRules(
        2200,
        10,
        (ContentType.REEL, ContentType.SHORT, ContentType.VIDEO, ContentType.CAROUSEL),
        (ContentType.REEL, ContentType.SHORT, ContentType.VIDEO),
    ),
    Platform.YOUTUBE: PlatformRules(
        5000, 15, (ContentType.SHORT, ContentType.VIDEO), (ContentType.SHORT, ContentType.VIDEO)
    ),
    Platform.LINKEDIN: PlatformRules(
        3000, 5, (ContentType.POST, ContentType.CAROUSEL, ContentType.VIDEO)
    ),
    Platform.PINTEREST: PlatformRules(500, 20, (ContentType.POST, ContentType.VIDEO)),
    Platform.X: PlatformRules(280, 3, (ContentType.POST, ContentType.VIDEO)),
}

VIDEO_TYPES = (ContentType.REEL, ContentType.SHORT, ContentType.VIDEO, ContentType.STORY)
PILLARS = (
    "educational",
    "promotional",
    "behind_the_scenes",
    "community",
    "product",
    "seasonal",
    "entertainment",
)

_TAG_RE = re.compile(r"[^\w]", re.UNICODE)


def clean_hashtags(tags: list[str], limit: int) -> list[str]:
    out: list[str] = []
    for t in tags:
        t = _TAG_RE.sub("", t.lstrip("#"))[:99]
        if t and t.lower() not in {o.lower() for o in out}:
            out.append(t)
    return out[:limit]


def unsupported_platforms(platforms: list[Platform], ctype: ContentType) -> list[Platform]:
    return [p for p in platforms if ctype not in RULES[p].types]


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", text.lower()) is not None


def check(
    *,
    ctype: ContentType,
    variants: list[dict],
    hook: str | None,
    has_media: bool,
    has_video: bool,
    words_to_avoid: list[str],
    topics_to_avoid: list[str],
    prefer_media: str,
    library_has_media: bool,
) -> list[dict[str, str]]:
    """Return human-readable warnings. Nothing here blocks saving; approval is the gate."""
    warnings: list[dict[str, str]] = []
    texts = [hook or ""] + [f"{v.get('caption') or ''} {v.get('cta') or ''}" for v in variants]
    blob = "\n".join(texts)
    for w in words_to_avoid:
        if w and _contains(blob, w):
            warnings.append(
                {
                    "code": "avoid_word",
                    "message": f"Uses \u201c{w}\u201d, which is on your list of words to avoid.",
                }
            )
    for t in topics_to_avoid:
        if t and _contains(blob, t):
            warnings.append(
                {
                    "code": "avoid_topic",
                    "message": f"Mentions \u201c{t}\u201d, a topic you asked to avoid.",
                }
            )
    for v in variants:
        rules = RULES[Platform(v["platform"])]
        if len(v.get("caption") or "") > rules.caption_max:
            msg = f"The {v['platform']} caption is too long (max {rules.caption_max})."
            warnings.append({"code": "caption_too_long", "message": msg})
    if ctype in VIDEO_TYPES and not has_video:
        warnings.append(
            {
                "code": "needs_video",
                "message": "This format needs a video. Attach one before it can publish.",
            }
        )
    elif not has_media:
        if prefer_media == "always" and library_has_media:
            warnings.append(
                {
                    "code": "needs_media",
                    "message": "No photo attached, but you asked to always use your own media.",
                }
            )
        else:
            warnings.append({"code": "no_media", "message": "No photo or video attached yet."})
    return warnings


# Allowed workflow moves (Phase 5 adds publishing/published/failed transitions).
EDITABLE = {
    ContentStatus.DRAFT,
    ContentStatus.READY,
    ContentStatus.AWAITING_APPROVAL,
    ContentStatus.APPROVED,
    ContentStatus.SCHEDULED,
    ContentStatus.REJECTED,
    ContentStatus.FAILED,
}
SUBMITTABLE = {ContentStatus.DRAFT, ContentStatus.READY, ContentStatus.REJECTED}
REJECTABLE = {ContentStatus.AWAITING_APPROVAL, ContentStatus.APPROVED, ContentStatus.SCHEDULED}
SCHEDULABLE = {
    ContentStatus.DRAFT,
    ContentStatus.READY,
    ContentStatus.AWAITING_APPROVAL,
    ContentStatus.APPROVED,
    ContentStatus.SCHEDULED,
    ContentStatus.REJECTED,
}
