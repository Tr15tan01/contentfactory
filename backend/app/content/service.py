"""Content lifecycle: AI generation, editing, approval, scheduling and version history.

Status flow (Phase 3):
  generating -> ready | failed           (AI job)
  draft/ready/rejected -> awaiting_approval -> approved -> scheduled
  editing an approved/scheduled post sends it back for approval when approval is required.
Publishing (scheduled -> publishing -> published) arrives with the Phase 5 publisher; until
then nothing in this module ever marks content as published.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import usage as ai_usage
from app.ai.base import AIProvider, AIProviderError, CompletionRequest, parse_json
from app.billing.entitlements import workspace_plan
from app.content import prompt as prompts
from app.content import rules
from app.core.errors import AppError, not_found
from app.core.security import utcnow
from app.intelligence import memory
from app.models import (
    AIUsage,
    Brand,
    BusinessProfile,
    Content,
    ContentMedia,
    ContentSchedule,
    ContentVariant,
    ContentVersion,
    MediaAsset,
    Product,
    Publication,
    SocialAccount,
    User,
    Workspace,
)
from app.models.enums import (
    AIOperation,
    ContentOrigin,
    ContentStatus,
    ContentType,
    MediaKind,
    MediaStatus,
    Platform,
    ScheduleStatus,
    SocialAccountStatus,
)
from app.schemas.content import (
    ContentListItem,
    ContentMediaOut,
    ContentOut,
    ContentPage,
    CreateIn,
    GenerateIn,
    GenerationInfo,
    PublicationOut,
    ScheduleOut,
    UpdateIn,
    VariantIn,
    VariantOut,
    VersionOut,
)
from app.services import audit
from app.storage import Storage
from app.workers.queue import JobQueue

log = logging.getLogger("contentfactory.content")
ACTIVE_SCHEDULE = (ScheduleStatus.PENDING, ScheduleStatus.QUEUED)
MEDIA_CANDIDATES = 40


# ----------------------------------------------------------------------------- loading
async def get_content(
    db: AsyncSession, ws: Workspace, content_id: uuid.UUID, *, lock: bool = False
) -> Content:
    q = select(Content).where(
        Content.id == content_id, Content.workspace_id == ws.id, Content.deleted_at.is_(None)
    )
    if lock:
        q = q.with_for_update()
    content = (await db.execute(q)).scalar_one_or_none()
    if content is None:
        raise not_found("Post")
    return content


async def _variants(db: AsyncSession, content_id: uuid.UUID) -> list[ContentVariant]:
    rows = await db.execute(
        select(ContentVariant)
        .where(ContentVariant.content_id == content_id)
        .order_by(ContentVariant.created_at)
    )
    return list(rows.scalars())


async def _media(
    db: AsyncSession, content_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[MediaAsset]]:
    if not content_ids:
        return {}
    rows = await db.execute(
        select(ContentMedia.content_id, MediaAsset)
        .join(MediaAsset, MediaAsset.id == ContentMedia.media_asset_id)
        .where(ContentMedia.content_id.in_(content_ids), MediaAsset.deleted_at.is_(None))
        .order_by(ContentMedia.position)
    )
    out: dict[uuid.UUID, list[MediaAsset]] = {}
    for cid, asset in rows.all():
        out.setdefault(cid, []).append(asset)
    return out


async def _schedules(
    db: AsyncSession, content_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[ContentSchedule]]:
    if not content_ids:
        return {}
    rows = await db.execute(
        select(ContentSchedule).where(
            ContentSchedule.content_id.in_(content_ids), ContentSchedule.status.in_(ACTIVE_SCHEDULE)
        )
    )
    out: dict[uuid.UUID, list[ContentSchedule]] = {}
    for s in rows.scalars():
        out.setdefault(s.content_id, []).append(s)
    return out


async def _ready_media(db: AsyncSession, ws: Workspace, ids: list[uuid.UUID]) -> list[MediaAsset]:
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []
    rows = (
        (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id.in_(ids),
                    MediaAsset.workspace_id == ws.id,
                    MediaAsset.deleted_at.is_(None),
                    MediaAsset.status == MediaStatus.READY,
                )
            )
        )
        .scalars()
        .all()
    )
    found = {a.id: a for a in rows}
    if len(found) != len(ids):
        raise AppError(
            422, "media_not_found", "One of the selected files isn't ready in your library."
        )
    return [found[i] for i in ids]


async def _set_media(db: AsyncSession, content: Content, assets: list[MediaAsset]) -> None:
    await db.execute(delete(ContentMedia).where(ContentMedia.content_id == content.id))
    for pos, a in enumerate(assets):
        db.add(
            ContentMedia(
                content_id=content.id,
                media_asset_id=a.id,
                position=pos,
                role="primary" if pos == 0 else "extra",
            )
        )


async def _brand_context(db: AsyncSession, ws: Workspace) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = (
        await db.execute(select(BusinessProfile).where(BusinessProfile.workspace_id == ws.id))
    ).scalar_one_or_none()
    brand = (
        await db.execute(select(Brand).where(Brand.workspace_id == ws.id))
    ).scalar_one_or_none()
    business = {
        "name": profile.name if profile else ws.name,
        "industry": profile.industry if profile else None,
        "description": profile.description if profile else None,
        "location": profile.location if profile else None,
        "website": profile.website if profile else None,
        "language": profile.preferred_language if profile else "en",
        "audience": profile.audience if profile else {},
        "unique_selling_points": profile.unique_selling_points if profile else [],
        "marketing_goals": profile.marketing_goals if profile else [],
        "topics_to_avoid": profile.topics_to_avoid if profile else [],
    }
    g = (brand.guidelines if brand else None) or {}
    brand_ctx = {
        "voice": brand.voice if brand else None,
        "tone": brand.tone if brand else [],
        "visual_style": brand.visual_style if brand else None,
        "words_to_use": g.get("words_to_use", []),
        "words_to_avoid": g.get("words_to_avoid", []),
    }
    return business, brand_ctx


# ----------------------------------------------------------------------------- serialization
def _schedule_out(schedules: list[ContentSchedule]) -> ScheduleOut | None:
    if not schedules:
        return None
    first = min(schedules, key=lambda s: s.scheduled_at)
    return ScheduleOut(
        scheduled_at=first.scheduled_at,
        platforms=[s.platform for s in schedules],
        status="queued" if all(s.status is ScheduleStatus.QUEUED for s in schedules) else "pending",
    )


def _thumb(storage: Storage, a: MediaAsset) -> str | None:
    if a.status is not MediaStatus.READY:
        return None
    return (
        storage.download_url(a.thumbnail_key)
        if a.thumbnail_key
        else (storage.download_url(a.storage_key) if a.kind is MediaKind.IMAGE else None)
    )


async def serialize(db: AsyncSession, storage: Storage, content: Content) -> ContentOut:
    await db.refresh(content)  # attributes expire on commit; reload before reading
    variants = await _variants(db, content.id)
    media = (await _media(db, [content.id])).get(content.id, [])
    schedules = (await _schedules(db, [content.id])).get(content.id, [])
    attrs = content.attributes or {}
    gen = attrs.get("generation") or {}
    pubs = (
        (
            await db.execute(
                select(Publication)
                .where(Publication.content_id == content.id)
                .order_by(Publication.created_at)
            )
        )
        .scalars()
        .all()
    )
    connected = set(
        (
            await db.execute(
                select(SocialAccount.platform).where(
                    SocialAccount.workspace_id == content.workspace_id,
                    SocialAccount.deleted_at.is_(None),
                    SocialAccount.status == SocialAccountStatus.CONNECTED,
                )
            )
        ).scalars()
    )
    return ContentOut(
        publications=[PublicationOut.model_validate(p, from_attributes=True) for p in pubs],
        missing_accounts=[v.platform for v in variants if v.platform not in connected],
        id=content.id,
        status=content.status,
        content_type=content.content_type,
        origin=content.origin,
        title=content.title,
        topic=content.topic,
        pillar=content.pillar,
        goal=content.goal,
        hook=content.hook,
        visual_concept=content.visual_concept,
        image_prompt=content.image_prompt,
        script=(content.video_script or {}).get("scenes") if content.video_script else None,
        slides=attrs.get("slides"),
        variants=[
            VariantOut(
                platform=v.platform,
                caption=v.caption or "",
                hashtags=list(v.hashtags or []),
                cta=v.cta,
            )
            for v in variants
        ],
        media=[
            ContentMediaOut(
                id=a.id,
                kind=a.kind.value,
                display_name=a.display_name,
                thumbnail_url=_thumb(storage, a),
                url=storage.download_url(a.storage_key) if a.status is MediaStatus.READY else None,
            )
            for a in media
        ],
        product_id=content.product_id,
        schedule=_schedule_out(schedules),
        approved_at=content.approved_at,
        rejected_reason=content.rejected_reason,
        warnings=attrs.get("warnings", []),
        generation=GenerationInfo(
            provider=gen.get("provider"),
            model=gen.get("model"),
            cached=bool(gen.get("cached")),
            error=attrs.get("generation_error"),
        ),
        version=int(attrs.get("version", 1)),
        created_at=content.created_at,
        updated_at=content.updated_at,
    )


# ----------------------------------------------------------------------------- warnings / versions
async def _refresh_warnings(db: AsyncSession, ws: Workspace, content: Content) -> None:
    variants = await _variants(db, content.id)
    media = (await _media(db, [content.id])).get(content.id, [])
    business, brand = await _brand_context(db, ws)
    library_has_media = (
        await db.execute(
            select(MediaAsset.id)
            .where(
                MediaAsset.workspace_id == ws.id,
                MediaAsset.deleted_at.is_(None),
                MediaAsset.status == MediaStatus.READY,
            )
            .limit(1)
        )
    ).first() is not None
    warnings = rules.check(
        ctype=content.content_type,
        variants=[
            {"platform": v.platform.value, "caption": v.caption, "cta": v.cta} for v in variants
        ],
        hook=content.hook,
        has_media=bool(media),
        has_video=any(a.kind is MediaKind.VIDEO for a in media),
        words_to_avoid=brand["words_to_avoid"],
        topics_to_avoid=business["topics_to_avoid"],
        prefer_media=(ws.settings or {}).get("prefer_media", "when_relevant"),
        library_has_media=library_has_media,
    )
    content.attributes = {**(content.attributes or {}), "warnings": warnings}


async def _snapshot(
    db: AsyncSession, content: Content, reason: str, user_id: uuid.UUID | None
) -> None:
    """Save the current state before a change. Versions are numbered per post."""
    variants = await _variants(db, content.id)
    media = (await _media(db, [content.id])).get(content.id, [])
    version = int((content.attributes or {}).get("version", 1))
    db.add(
        ContentVersion(
            content_id=content.id,
            version=version,
            reason=reason,
            created_by_id=user_id,
            snapshot={
                "title": content.title,
                "hook": content.hook,
                "pillar": content.pillar,
                "visual_concept": content.visual_concept,
                "image_prompt": content.image_prompt,
                "video_script": content.video_script,
                "slides": (content.attributes or {}).get("slides"),
                "variants": [
                    {
                        "platform": v.platform.value,
                        "caption": v.caption,
                        "hashtags": list(v.hashtags or []),
                        "cta": v.cta,
                    }
                    for v in variants
                ],
                "media_ids": [str(a.id) for a in media],
            },
        )
    )
    content.attributes = {**(content.attributes or {}), "version": version + 1}


def _approval_required(ws: Workspace) -> bool:
    return bool((ws.settings or {}).get("approval_required", True))


async def _invalidate_approval(db: AsyncSession, ws: Workspace, content: Content) -> None:
    """A changed post needs fresh approval (unless the workspace publishes without approval)."""
    if content.status in (ContentStatus.APPROVED, ContentStatus.SCHEDULED) and _approval_required(
        ws
    ):
        content.status = ContentStatus.AWAITING_APPROVAL
        content.approved_at = None
        content.approved_by_id = None
        await _set_schedule_state(db, content, ScheduleStatus.PENDING)
    elif content.status is ContentStatus.REJECTED:
        content.status = ContentStatus.READY
        content.rejected_reason = None


async def _set_schedule_state(db: AsyncSession, content: Content, state: ScheduleStatus) -> None:
    for s in (await _schedules(db, [content.id])).get(content.id, []):
        s.status = state


def _after_approval_status(has_schedule: bool) -> ContentStatus:
    return ContentStatus.SCHEDULED if has_schedule else ContentStatus.APPROVED


# ----------------------------------------------------------------------------- generation
def _unsupported(ctype: ContentType, bad: list[Platform]) -> AppError:
    names = ", ".join(p.value for p in bad)
    return AppError(
        422, "unsupported_format", f"{ctype.value.capitalize()} posts aren't supported on {names}."
    )


async def start_generation(
    db: AsyncSession,
    ws: Workspace,
    user: User,
    body: GenerateIn,
    queue: JobQueue,
    provider: AIProvider,
) -> Content:
    bad = rules.unsupported_platforms(body.platforms, body.content_type)
    if bad:
        raise _unsupported(body.content_type, bad)
    if body.product_id:
        product = await db.get(Product, body.product_id)
        if product is None or product.workspace_id != ws.id or product.deleted_at is not None:
            raise not_found("Product")
    await _ready_media(db, ws, body.media_ids)
    if body.scheduled_at:
        _validate_time(body.scheduled_at)

    content = Content(
        workspace_id=ws.id,
        created_by_id=user.id,
        product_id=body.product_id,
        status=ContentStatus.GENERATING,
        content_type=body.content_type,
        origin=ContentOrigin.AI,
        title=(body.idea or "New post")[:200],
        topic=(body.idea or None) and body.idea[:300],
        goal=body.goal,
        hashtags=[],
        attributes={"version": 1, "request": body.model_dump(mode="json")},
    )
    db.add(content)
    await db.flush()
    usage = await ai_usage.reserve(
        db,
        ws,
        user_id=user.id,
        operation=AIOperation.TEXT,
        provider=provider.name,
        model=provider.model_for("fast"),
        content_id=content.id,
    )
    audit.record(
        db,
        "content.generation_started",
        actor_user_id=user.id,
        workspace_id=ws.id,
        data={"content_id": str(content.id)},
    )
    await db.commit()
    await queue.enqueue("generate_content", content_id=str(content.id), usage_id=str(usage.id))
    return content


async def run_generation(
    db: AsyncSession, provider: AIProvider, content_id: uuid.UUID, usage_id: uuid.UUID
) -> Content | None:
    """Worker job body. Always ends with the usage committed or refunded."""
    content = await db.get(Content, content_id)
    usage = await db.get(AIUsage, usage_id)
    if content is None or usage is None or usage.status.value != "reserved":
        return content
    ws = await db.get(Workspace, content.workspace_id)
    assert ws is not None
    req = (content.attributes or {}).get("request", {})
    try:
        body = GenerateIn.model_validate(req)
        platforms = body.platforms
        business, brand = await _brand_context(db, ws)
        product_ctx = None
        if content.product_id:
            p = await db.get(Product, content.product_id)
            if p and p.deleted_at is None:
                product_ctx = {
                    "name": p.name,
                    "description": p.description,
                    "price": f"{p.price} {p.currency}" if p.price is not None else None,
                    "benefits": p.benefits,
                }
        prefer = (ws.settings or {}).get("prefer_media", "when_relevant")
        explicit = await _ready_media(db, ws, body.media_ids) if body.media_ids else []
        candidates: list[MediaAsset] = []
        if not explicit and prefer != "never":
            candidates = list(
                (
                    await db.execute(
                        select(MediaAsset)
                        .where(
                            MediaAsset.workspace_id == ws.id,
                            MediaAsset.deleted_at.is_(None),
                            MediaAsset.status == MediaStatus.READY,
                        )
                        .order_by(MediaAsset.is_favorite.desc(), MediaAsset.created_at.desc())
                        .limit(MEDIA_CANDIDATES)
                    )
                ).scalars()
            )
            if body.content_type in rules.VIDEO_TYPES:
                candidates = [a for a in candidates if a.kind is MediaKind.VIDEO] or candidates
        media_ctx = [
            {
                "id": str(a.id),
                "kind": a.kind.value,
                "name": a.display_name,
                "tags": a.tags,
                "description": a.alt_text,
            }
            for a in candidates
        ]
        instruction = req.get("instruction")
        topic = " ".join(
            filter(
                None,
                [body.idea, (product_ctx or {}).get("name"), body.goal, body.content_type.value],
            )
        )
        learned = [m.content for m in await memory.for_prompt(db, ws.id, topic)]
        prompt, hints = prompts.build(
            business=business,
            brand=brand,
            product=product_ctx,
            media=media_ctx,
            prefer_media=prefer,
            brief={"idea": body.idea, "goal": body.goal},
            platforms=platforms,
            ctype=body.content_type,
            instruction=instruction,
            learned=learned,
        )
        model = provider.model_for("fast")
        fp = prompts.fingerprint(provider.name, model, prompts.SYSTEM, prompt)
        usage.request_fingerprint = fp
        cached = await ai_usage.cache_get(db, ws.id, fp)
        completion = None
        if cached is not None:
            data = cached
        else:
            completion = await provider.complete(
                CompletionRequest(
                    role="fast", system=prompts.SYSTEM, prompt=prompt, max_tokens=2500, hints=hints
                )
            )
            try:
                data = parse_json(completion.text)
            except ValueError:
                # One repair attempt: ask for the JSON only.
                completion = await provider.complete(
                    CompletionRequest(
                        role="fast",
                        system=prompts.SYSTEM,
                        prompt=prompt + "\n\nReturn only the JSON object.",
                        max_tokens=2500,
                        temperature=0.2,
                        hints=hints,
                    )
                )
                data = parse_json(completion.text)
            await ai_usage.cache_put(db, ws.id, fp, completion.provider, completion.model, data)

        await _apply_draft(
            db, ws, content, data, platforms, explicit, {str(a.id): a for a in candidates}
        )
        after = (content.attributes or {}).get("after_generation")
        content.status = (
            ContentStatus.AWAITING_APPROVAL if after == "awaiting_approval" else ContentStatus.READY
        )
        content.attributes = {
            **(content.attributes or {}),
            "generation": {
                "provider": (completion.provider if completion else provider.name),
                "model": (completion.model if completion else model),
                "cached": cached is not None,
            },
            "generation_error": None,
        }
        await _refresh_warnings(db, ws, content)
        if body.scheduled_at and not (await _schedules(db, [content.id])).get(content.id):
            for p in platforms:
                db.add(
                    ContentSchedule(
                        workspace_id=ws.id,
                        content_id=content.id,
                        platform=p,
                        scheduled_at=body.scheduled_at,
                        status=ScheduleStatus.PENDING,
                    )
                )
        ai_usage.commit(usage, completion, cache_hit=cached is not None)
        await _log_draft(
            db,
            content,
            usage,
            ok=True,
            learned=len(learned),
            cached=cached is not None,
            platforms=platforms,
        )
        await db.commit()
    except (AIProviderError, ValueError, KeyError, TypeError) as exc:
        await db.rollback()
        content = await db.get(Content, content_id)
        usage = await db.get(AIUsage, usage_id)
        assert content is not None and usage is not None
        log.warning("generation failed for %s: %s", content_id, exc)
        message = (
            str(exc)
            if isinstance(exc, AIProviderError)
            else "The draft came back in an unexpected format."
        )
        content.status = ContentStatus.FAILED
        content.attributes = {
            **(content.attributes or {}),
            "generation_error": f"{message} Your allowance wasn't used.",
        }
        ai_usage.refund(usage)
        await _log_draft(db, content, usage, ok=False, error=message)
        await db.commit()
    return content


async def _log_draft(
    db: AsyncSession,
    content: Content,
    usage: AIUsage,
    *,
    ok: bool,
    learned: int = 0,
    cached: bool = False,
    platforms: list[Platform] | None = None,
    error: str | None = None,
) -> None:
    from app.agents import activity
    from app.models.enums import AgentKind, AgentRunStatus, AgentTrigger

    run = await activity.start(
        db,
        content.workspace_id,
        AgentKind.CONTENT,
        f"Draft \u201c{content.title}\u201d",
        trigger=AgentTrigger.USER,
        user_id=usage.user_id,
        data={"content_id": str(content.id)},
    )
    if not ok:
        await activity.step(db, run, "Draft failed", detail=error, status=AgentRunStatus.FAILED)
        activity.finish(run, AgentRunStatus.FAILED, error or "The draft failed.", error=error)
        return
    await activity.step(
        db,
        run,
        "Read the business profile and brand voice",
        detail=f"{learned} memories used" if learned else "No memories yet",
        kind="decision",
    )
    media = (await _media(db, [content.id])).get(content.id, [])
    await activity.step(
        db,
        run,
        f"Chose \u201c{media[0].display_name}\u201d from your library"
        if media
        else "No library photo fitted this post",
        kind="decision",
    )
    names = ", ".join(p.value.capitalize() for p in platforms or [])
    await activity.step(
        db,
        run,
        f"Wrote the post for {names}"
        + (" (reused an identical earlier draft, no charge)" if cached else ""),
        cost=float(usage.estimated_cost_usd or 0),
    )
    activity.finish(run, AgentRunStatus.SUCCEEDED, f"Ready for review: {content.title}")


async def _apply_draft(
    db: AsyncSession,
    ws: Workspace,
    content: Content,
    data: dict[str, Any],
    platforms: list[Platform],
    explicit: list[MediaAsset],
    candidates: dict[str, MediaAsset],
) -> None:
    by_platform = {
        str(v.get("platform")): v for v in data.get("variants") or [] if isinstance(v, dict)
    }
    fallback = next(iter(by_platform.values()), {})
    await db.execute(delete(ContentVariant).where(ContentVariant.content_id == content.id))
    for p in platforms:
        v = by_platform.get(p.value, fallback)
        r = rules.RULES[p]
        caption = str(v.get("caption") or "").strip()
        db.add(
            ContentVariant(
                content_id=content.id,
                platform=p,
                caption=caption[: r.caption_max],
                hashtags=rules.clean_hashtags(
                    [str(t) for t in v.get("hashtags") or []], r.hashtags_max
                ),
                cta=(str(v.get("cta") or "").strip()[:300] or None),
            )
        )
    title = str(data.get("title") or content.title).strip()[:200]
    pillar = str(data.get("pillar") or "").strip().lower()
    visual = data.get("visual") if isinstance(data.get("visual"), dict) else {}
    content.title = title or content.title
    content.pillar = pillar if pillar in rules.PILLARS else None
    content.hook = str(data.get("hook") or "").strip() or None
    content.visual_concept = str(visual.get("concept") or "").strip() or None
    content.image_prompt = str(visual.get("image_prompt") or "").strip() or None
    first = by_platform.get(platforms[0].value, fallback)
    content.caption = str(first.get("caption") or "")[:10000]
    content.cta = str(first.get("cta") or "")[:300] or None
    script = data.get("script")
    content.video_script = {"scenes": script} if isinstance(script, list) and script else None
    slides = data.get("slides")
    content.attributes = {
        **(content.attributes or {}),
        "slides": slides if isinstance(slides, list) and slides else None,
    }
    # Media: what the user chose wins; otherwise only an ID we actually offered is accepted.
    chosen = explicit
    if not chosen:
        mid = visual.get("media_id")
        if isinstance(mid, str) and mid in candidates:
            chosen = [candidates[mid]]
    await _set_media(db, content, chosen)
    await db.flush()


async def regenerate(
    db: AsyncSession,
    ws: Workspace,
    user: User,
    content_id: uuid.UUID,
    instruction: str | None,
    queue: JobQueue,
    provider: AIProvider,
) -> Content:
    content = await get_content(db, ws, content_id, lock=True)
    if content.status not in rules.EDITABLE:
        raise AppError(409, "not_editable", "This post can't be changed right now.")
    await _snapshot(db, content, "regenerate", user.id)
    req = dict((content.attributes or {}).get("request") or {})
    if not req:  # manually written post: build a brief from it
        variants = await _variants(db, content.id)
        req = {
            "idea": content.title,
            "platforms": [v.platform.value for v in variants] or ["instagram"],
            "content_type": content.content_type.value,
        }
    req["instruction"] = instruction
    req.pop("scheduled_at", None)
    await _invalidate_approval(db, ws, content)
    # A post that was already in the approval queue goes back there once redrafted.
    after = content.status.value if content.status is ContentStatus.AWAITING_APPROVAL else "ready"
    content.status = ContentStatus.GENERATING
    content.attributes = {
        **(content.attributes or {}),
        "request": req,
        "generation_error": None,
        "after_generation": after,
    }
    usage = await ai_usage.reserve(
        db,
        ws,
        user_id=user.id,
        operation=AIOperation.TEXT,
        provider=provider.name,
        model=provider.model_for("fast"),
        content_id=content.id,
    )
    await db.commit()
    await queue.enqueue("generate_content", content_id=str(content.id), usage_id=str(usage.id))
    return content


# ----------------------------------------------------------------------------- manual create / edit
async def create_manual(db: AsyncSession, ws: Workspace, user: User, body: CreateIn) -> Content:
    bad = rules.unsupported_platforms(body.platforms, body.content_type)
    if bad:
        raise _unsupported(body.content_type, bad)
    media = await _ready_media(db, ws, body.media_ids)
    content = Content(
        workspace_id=ws.id,
        created_by_id=user.id,
        product_id=body.product_id,
        status=ContentStatus.READY,
        content_type=body.content_type,
        origin=ContentOrigin.MANUAL,
        title=body.title.strip(),
        hook=body.hook,
        caption=body.caption,
        cta=body.cta,
        hashtags=[],
        attributes={"version": 1},
    )
    db.add(content)
    await db.flush()
    for p in body.platforms:
        r = rules.RULES[p]
        db.add(
            ContentVariant(
                content_id=content.id,
                platform=p,
                caption=body.caption,
                hashtags=rules.clean_hashtags(body.hashtags, r.hashtags_max),
                cta=body.cta,
            )
        )
    await _set_media(db, content, media)
    await db.flush()
    await _refresh_warnings(db, ws, content)
    await db.commit()
    return content


async def update(
    db: AsyncSession, ws: Workspace, user: User, content_id: uuid.UUID, body: UpdateIn
) -> Content:
    content = await get_content(db, ws, content_id, lock=True)
    if content.status not in rules.EDITABLE:
        raise AppError(
            409,
            "not_editable",
            "This post can't be edited while it's being generated or published.",
        )
    await _snapshot(db, content, "edit", user.id)
    if body.title is not None:
        content.title = body.title.strip()
    if body.hook is not None:
        content.hook = body.hook.strip() or None
    if body.visual_concept is not None:
        content.visual_concept = body.visual_concept.strip() or None
    if body.script is not None:
        content.video_script = {"scenes": body.script} if body.script else None
    if body.slides is not None:
        content.attributes = {**(content.attributes or {}), "slides": body.slides or None}
    if body.variants is not None:
        await _replace_variants(db, content, body.variants)
    if body.media_ids is not None:
        await _set_media(db, content, await _ready_media(db, ws, body.media_ids))
    if content.status is ContentStatus.FAILED:
        content.status = ContentStatus.READY
        content.attributes = {**(content.attributes or {}), "generation_error": None}
    await _invalidate_approval(db, ws, content)
    await db.flush()
    await _refresh_warnings(db, ws, content)
    await db.commit()
    return content


async def _replace_variants(db: AsyncSession, content: Content, variants: list[VariantIn]) -> None:
    platforms = [v.platform for v in variants]
    if len(set(platforms)) != len(platforms):
        raise AppError(422, "duplicate_platform", "Each platform can only appear once.")
    bad = rules.unsupported_platforms(platforms, content.content_type)
    if bad:
        raise AppError(
            422,
            "unsupported_format",
            f"This format isn't supported on {', '.join(p.value for p in bad)}.",
        )
    await db.execute(delete(ContentVariant).where(ContentVariant.content_id == content.id))
    for v in variants:
        r = rules.RULES[v.platform]
        db.add(
            ContentVariant(
                content_id=content.id,
                platform=v.platform,
                caption=v.caption,
                hashtags=rules.clean_hashtags(v.hashtags, r.hashtags_max),
                cta=(v.cta or "").strip() or None,
            )
        )
    first = variants[0]
    content.caption, content.cta = first.caption, first.cta
    # Schedules follow the platform list.
    schedules = (await _schedules(db, [content.id])).get(content.id, [])
    if schedules:
        when, state = schedules[0].scheduled_at, schedules[0].status
        keep = {s.platform for s in schedules} & set(platforms)
        for s in schedules:
            if s.platform not in keep:
                s.status = ScheduleStatus.CANCELLED
        for p in set(platforms) - keep:
            db.add(
                ContentSchedule(
                    workspace_id=content.workspace_id,
                    content_id=content.id,
                    platform=p,
                    scheduled_at=when,
                    status=state,
                )
            )


# ----------------------------------------------------------------------------- workflow
async def submit(db: AsyncSession, ws: Workspace, user: User, content_id: uuid.UUID) -> Content:
    content = await get_content(db, ws, content_id, lock=True)
    if content.status not in rules.SUBMITTABLE:
        raise AppError(409, "invalid_transition", "Only drafts can be sent for approval.")
    has_schedule = bool((await _schedules(db, [content.id])).get(content.id))
    if _approval_required(ws):
        content.status = ContentStatus.AWAITING_APPROVAL
    else:
        content.status = _after_approval_status(has_schedule)
        content.approved_at, content.approved_by_id = utcnow(), user.id
        await _set_schedule_state(db, content, ScheduleStatus.QUEUED)
    content.rejected_reason = None
    audit.record(
        db,
        "content.submitted",
        actor_user_id=user.id,
        workspace_id=ws.id,
        data={"content_id": str(content.id)},
    )
    await db.commit()
    return content


async def approve(db: AsyncSession, ws: Workspace, user: User, content_id: uuid.UUID) -> Content:
    content = await get_content(db, ws, content_id, lock=True)
    if content.status not in (
        ContentStatus.AWAITING_APPROVAL,
        ContentStatus.READY,
        ContentStatus.DRAFT,
        ContentStatus.REJECTED,
    ):
        raise AppError(409, "invalid_transition", "This post isn't waiting for approval.")
    if not (await _variants(db, content.id)):
        raise AppError(409, "nothing_to_approve", "Add a caption for at least one platform first.")
    schedules = (await _schedules(db, [content.id])).get(content.id, [])
    if schedules and min(s.scheduled_at for s in schedules) <= utcnow():
        raise AppError(
            409, "schedule_in_past", "The scheduled time has passed. Pick a new time, then approve."
        )
    content.status = _after_approval_status(bool(schedules))
    content.approved_at, content.approved_by_id, content.rejected_reason = utcnow(), user.id, None
    await _set_schedule_state(db, content, ScheduleStatus.QUEUED)
    audit.record(
        db,
        "content.approved",
        actor_user_id=user.id,
        workspace_id=ws.id,
        data={"content_id": str(content.id)},
    )
    await db.commit()
    return content


async def reject(
    db: AsyncSession, ws: Workspace, user: User, content_id: uuid.UUID, reason: str | None
) -> Content:
    content = await get_content(db, ws, content_id, lock=True)
    if content.status not in rules.REJECTABLE:
        raise AppError(
            409,
            "invalid_transition",
            "Only posts waiting for approval or approved can be rejected.",
        )
    content.status = ContentStatus.REJECTED
    content.rejected_reason = (reason or "").strip() or None
    content.approved_at = content.approved_by_id = None
    await _set_schedule_state(db, content, ScheduleStatus.PENDING)
    audit.record(
        db,
        "content.rejected",
        actor_user_id=user.id,
        workspace_id=ws.id,
        data={"content_id": str(content.id)},
    )
    await db.commit()
    return content


def _validate_time(when: datetime) -> None:
    now = utcnow()
    if when < now + timedelta(minutes=5):
        raise AppError(422, "schedule_too_soon", "Pick a time at least 5 minutes from now.")
    if when > now + timedelta(days=366):
        raise AppError(422, "schedule_too_far", "Posts can be scheduled up to a year ahead.")


async def _check_schedule_quota(
    db: AsyncSession, ws: Workspace, content_id: uuid.UUID, when: datetime
) -> None:
    plan = await workspace_plan(db, ws)
    start = when.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=32)).replace(day=1)
    count = (
        await db.execute(
            select(func.count(func.distinct(ContentSchedule.content_id))).where(
                ContentSchedule.workspace_id == ws.id,
                ContentSchedule.status.in_(ACTIVE_SCHEDULE),
                ContentSchedule.scheduled_at >= start,
                ContentSchedule.scheduled_at < end,
                ContentSchedule.content_id != content_id,
            )
        )
    ).scalar_one()
    if count >= plan.scheduled_posts:
        raise AppError(
            402,
            "quota_exceeded",
            f"Your plan allows {plan.scheduled_posts} scheduled posts a month, "
            f"and {start.strftime('%B')} is full.",
            {"bucket": "scheduled_posts", "limit": plan.scheduled_posts},
        )


async def schedule(
    db: AsyncSession, ws: Workspace, user: User, content_id: uuid.UUID, when: datetime
) -> Content:
    content = await get_content(db, ws, content_id, lock=True)
    if content.status not in rules.SCHEDULABLE:
        raise AppError(409, "invalid_transition", "This post can't be scheduled right now.")
    _validate_time(when)
    await _check_schedule_quota(db, ws, content.id, when)
    variants = await _variants(db, content.id)
    if not variants:
        raise AppError(409, "nothing_to_schedule", "Add a caption for at least one platform first.")
    approved = content.status in (ContentStatus.APPROVED, ContentStatus.SCHEDULED)
    state = ScheduleStatus.QUEUED if approved else ScheduleStatus.PENDING
    existing = {s.platform: s for s in (await _schedules(db, [content.id])).get(content.id, [])}
    for v in variants:
        if v.platform in existing:
            existing[v.platform].scheduled_at, existing[v.platform].status = when, state
        else:
            db.add(
                ContentSchedule(
                    workspace_id=ws.id,
                    content_id=content.id,
                    platform=v.platform,
                    scheduled_at=when,
                    status=state,
                )
            )
    if approved:
        content.status = ContentStatus.SCHEDULED
    audit.record(
        db,
        "content.scheduled",
        actor_user_id=user.id,
        workspace_id=ws.id,
        data={"content_id": str(content.id), "at": when.isoformat()},
    )
    await db.commit()
    return content


async def unschedule(db: AsyncSession, ws: Workspace, content_id: uuid.UUID) -> Content:
    content = await get_content(db, ws, content_id, lock=True)
    await _set_schedule_state(db, content, ScheduleStatus.CANCELLED)
    if content.status is ContentStatus.SCHEDULED:
        content.status = ContentStatus.APPROVED
    await db.commit()
    return content


async def duplicate(db: AsyncSession, ws: Workspace, user: User, content_id: uuid.UUID) -> Content:
    src = await get_content(db, ws, content_id)
    if src.status is ContentStatus.GENERATING:
        raise AppError(409, "not_ready", "Wait for the draft to finish first.")
    copy = Content(
        workspace_id=ws.id,
        created_by_id=user.id,
        product_id=src.product_id,
        status=ContentStatus.READY,
        content_type=src.content_type,
        origin=src.origin,
        title=f"{src.title} (copy)"[:200],
        topic=src.topic,
        pillar=src.pillar,
        goal=src.goal,
        hook=src.hook,
        caption=src.caption,
        cta=src.cta,
        hashtags=list(src.hashtags or []),
        visual_concept=src.visual_concept,
        image_prompt=src.image_prompt,
        video_script=src.video_script,
        attributes={
            "version": 1,
            "slides": (src.attributes or {}).get("slides"),
            "warnings": (src.attributes or {}).get("warnings", []),
            "request": (src.attributes or {}).get("request"),
        },
    )
    db.add(copy)
    await db.flush()
    for v in await _variants(db, src.id):
        db.add(
            ContentVariant(
                content_id=copy.id,
                platform=v.platform,
                caption=v.caption,
                hashtags=list(v.hashtags or []),
                cta=v.cta,
            )
        )
    await _set_media(db, copy, (await _media(db, [src.id])).get(src.id, []))
    await db.commit()
    return copy


async def remove(db: AsyncSession, ws: Workspace, user: User, content_id: uuid.UUID) -> None:
    content = await get_content(db, ws, content_id, lock=True)
    if content.status in (ContentStatus.PUBLISHING,):
        raise AppError(409, "publishing", "This post is being published and can't be deleted now.")
    await _set_schedule_state(db, content, ScheduleStatus.CANCELLED)
    content.deleted_at = utcnow()
    audit.record(
        db,
        "content.deleted",
        actor_user_id=user.id,
        workspace_id=ws.id,
        data={"content_id": str(content.id), "title": content.title},
    )
    await db.commit()


# ----------------------------------------------------------------------------- versions
async def versions(db: AsyncSession, ws: Workspace, content_id: uuid.UUID) -> list[VersionOut]:
    await get_content(db, ws, content_id)
    rows = await db.execute(
        select(ContentVersion, User.full_name, User.email)
        .outerjoin(User, User.id == ContentVersion.created_by_id)
        .where(ContentVersion.content_id == content_id)
        .order_by(ContentVersion.version.desc())
    )
    return [
        VersionOut(
            version=v.version,
            reason=v.reason,
            created_at=v.created_at,
            created_by=name or email,
            title=v.snapshot.get("title", ""),
            hook=v.snapshot.get("hook"),
        )
        for v, name, email in rows.all()
    ]


async def restore(
    db: AsyncSession, ws: Workspace, user: User, content_id: uuid.UUID, version: int
) -> Content:
    content = await get_content(db, ws, content_id, lock=True)
    if content.status not in rules.EDITABLE:
        raise AppError(409, "not_editable", "This post can't be changed right now.")
    snap = (
        await db.execute(
            select(ContentVersion.snapshot).where(
                ContentVersion.content_id == content.id, ContentVersion.version == version
            )
        )
    ).scalar_one_or_none()
    if snap is None:
        raise not_found("Version")
    await _snapshot(db, content, "restore", user.id)
    content.title, content.hook, content.pillar = (
        snap.get("title") or content.title,
        snap.get("hook"),
        snap.get("pillar"),
    )
    content.visual_concept, content.image_prompt, content.video_script = (
        snap.get("visual_concept"),
        snap.get("image_prompt"),
        snap.get("video_script"),
    )
    content.attributes = {**(content.attributes or {}), "slides": snap.get("slides")}
    await _replace_variants(
        db,
        content,
        [VariantIn.model_validate(v) for v in snap.get("variants") or []]
        or [VariantIn(platform=Platform.INSTAGRAM)],
    )
    media_ids = [uuid.UUID(m) for m in snap.get("media_ids") or []]
    live = (
        (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id.in_(media_ids or [uuid.uuid4()]), MediaAsset.deleted_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )
    await _set_media(db, content, [a for a in live if a.workspace_id == ws.id])
    await _invalidate_approval(db, ws, content)
    await db.flush()
    await _refresh_warnings(db, ws, content)
    await db.commit()
    return content


# ----------------------------------------------------------------------------- listing
async def list_content(
    db: AsyncSession,
    storage: Storage,
    ws: Workspace,
    *,
    status: list[ContentStatus] | None = None,
    platform: Platform | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    unscheduled: bool = False,
    q: str | None = None,
    limit: int = 100,
) -> ContentPage:
    conds: list[Any] = [Content.workspace_id == ws.id, Content.deleted_at.is_(None)]
    if status:
        conds.append(Content.status.in_(status))
    if q and q.strip():
        term = f"%{q.strip().replace('%', r'\%').replace('_', r'\_')}%"
        conds.append(
            Content.title.ilike(term) | Content.hook.ilike(term) | Content.caption.ilike(term)
        )
    if platform:
        conds.append(
            Content.id.in_(
                select(ContentVariant.content_id).where(ContentVariant.platform == platform)
            )
        )
    sched = select(ContentSchedule.content_id).where(ContentSchedule.status.in_(ACTIVE_SCHEDULE))
    if start or end:
        if start:
            sched = sched.where(ContentSchedule.scheduled_at >= start)
        if end:
            sched = sched.where(ContentSchedule.scheduled_at < end)
        conds.append(Content.id.in_(sched))
    elif unscheduled:
        conds.append(Content.id.not_in(sched))
    total = (await db.execute(select(func.count()).select_from(Content).where(*conds))).scalar_one()
    rows = list(
        (
            await db.execute(
                select(Content).where(*conds).order_by(Content.updated_at.desc()).limit(limit)
            )
        ).scalars()
    )
    ids = [c.id for c in rows]
    schedules = await _schedules(db, ids)
    media = await _media(db, ids)
    variant_rows = await db.execute(
        select(ContentVariant.content_id, ContentVariant.platform).where(
            ContentVariant.content_id.in_(ids or [uuid.uuid4()])
        )
    )
    platforms: dict[uuid.UUID, list[Platform]] = {}
    for cid, p in variant_rows.all():
        platforms.setdefault(cid, []).append(p)
    items = []
    for c in rows:
        s = _schedule_out(schedules.get(c.id, []))
        first = (media.get(c.id) or [None])[0]
        items.append(
            ContentListItem(
                id=c.id,
                title=c.title,
                status=c.status,
                content_type=c.content_type,
                pillar=c.pillar,
                platforms=platforms.get(c.id, []),
                scheduled_at=s.scheduled_at if s else None,
                thumbnail_url=_thumb(storage, first) if first else None,
                warnings=len((c.attributes or {}).get("warnings", [])),
                updated_at=c.updated_at,
            )
        )
    if start or end:
        items.sort(key=lambda i: i.scheduled_at or datetime.max.replace(tzinfo=i.updated_at.tzinfo))
    return ContentPage(items=items, total=total)
