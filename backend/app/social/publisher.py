"""Publishing engine.

`enqueue_due` (every minute) turns due, approved schedules into Publication rows with a unique
idempotency key, so a schedule can never produce two publications. `publish` (a job per
publication) talks to the platform. Rules:

* A publication is `published` only when the platform returned a post id.
* Before calling the platform the row is marked `publishing` and committed. If a worker dies
  mid-call, the outcome is unknown: after 15 minutes the sweep marks it failed with
  `unknown_outcome` and asks a person to check, instead of risking a duplicate post.
* Temporary errors retry with backoff (1 min, 5 min, 15 min, 1 h, 3 h); platform-side
  processing (videos) is polled every 30 s for up to 30 minutes.
* Expired or revoked access flags the account for reconnect and fails the publication.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import InvalidToken
from app.core.security import utcnow
from app.models import (
    Content,
    ContentMedia,
    ContentSchedule,
    ContentVariant,
    MediaAsset,
    Publication,
    SocialAccount,
)
from app.models.enums import (
    ContentStatus,
    MediaKind,
    MediaStatus,
    PublicationStatus,
    ScheduleStatus,
    SocialAccountStatus,
    WorkspaceRole,
)
from app.services import audit
from app.social import registry
from app.social.base import MediaItem, PublishRequest, SocialError
from app.social.service import PLATFORM_LABEL, mark_needs_reauth, token_row, token_set
from app.storage import get_storage
from app.workers.queue import JobQueue

log = logging.getLogger("contentfactory.publisher")
BACKOFF_SECONDS = [60, 300, 900, 3600, 10800]
PROCESSING_POLL_SECONDS = 30
MAX_PROCESSING_POLLS = 60
UNKNOWN_OUTCOME_AFTER = timedelta(minutes=15)


def idempotency_key(schedule: ContentSchedule, account_id: uuid.UUID | None) -> str:
    when = schedule.scheduled_at.isoformat()
    raw = f"{schedule.content_id}:{schedule.platform.value}:{account_id}:{when}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _job_id(pub: Publication) -> str:
    return f"publish:{pub.id}:{pub.retry_count}:{pub.provider_state.get('polls', 0)}"


async def enqueue_due(db: AsyncSession, queue: JobQueue) -> dict[str, int]:
    now = utcnow()
    stats = {"queued": 0, "overdue": 0, "unknown": 0}

    # Unapproved posts whose time has come are flagged, never published.
    overdue = await db.execute(
        update(ContentSchedule)
        .where(
            ContentSchedule.status == ScheduleStatus.PENDING, ContentSchedule.scheduled_at <= now
        )
        .values(status=ScheduleStatus.APPROVAL_OVERDUE)
        .returning(ContentSchedule.id)
    )
    overdue_ids = [row[0] for row in overdue.all()]
    stats["overdue"] = len(overdue_ids)
    if overdue_ids:
        from app.models.enums import NotificationType
        from app.notifications.service import notify

        rows = (
            await db.execute(
                select(ContentSchedule.content_id, ContentSchedule.workspace_id, Content.title)
                .join(Content, Content.id == ContentSchedule.content_id)
                .where(ContentSchedule.id.in_(overdue_ids))
            )
        ).all()
        for content_id, ws_id, title in {r[0]: r for r in rows}.values():
            await notify(
                db,
                workspace_id=ws_id,
                kind=NotificationType.APPROVAL_OVERDUE,
                title=f"\u201c{title}\u201d missed its time",
                body="It wasn't approved in time, so it wasn't published. "
                "Approve it and pick a new time.",
                action_url=f"/content/{content_id}",
                dedupe=f"overdue:{content_id}",
                priority="high",
                entity=("content", content_id),
            )

    # Workers that died mid-call: don't guess, ask a person.
    stuck = (
        (
            await db.execute(
                select(Publication)
                .where(
                    Publication.status == PublicationStatus.PUBLISHING,
                    Publication.last_attempt_at < now - UNKNOWN_OUTCOME_AFTER,
                )
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    for pub in stuck:
        _fail(
            pub,
            "unknown_outcome",
            "We lost contact with the platform while publishing. "
            "Check your account: if the post isn't there, retry.",
        )
        stats["unknown"] += 1

    due = (
        (
            await db.execute(
                select(ContentSchedule)
                .join(Content, Content.id == ContentSchedule.content_id)
                .where(
                    ContentSchedule.status == ScheduleStatus.QUEUED,
                    ContentSchedule.scheduled_at <= now + timedelta(seconds=30),
                    Content.status.in_([ContentStatus.SCHEDULED, ContentStatus.PUBLISHING]),
                    Content.deleted_at.is_(None),
                )
                .with_for_update(of=ContentSchedule, skip_locked=True)
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    for schedule in due:
        account = await _account_for(db, schedule)
        key = idempotency_key(schedule, account.id if account else None)
        variant = (
            await db.execute(
                select(ContentVariant.id).where(
                    ContentVariant.content_id == schedule.content_id,
                    ContentVariant.platform == schedule.platform,
                )
            )
        ).scalar_one_or_none()
        pub_id = (
            await db.execute(
                insert(Publication)
                .values(
                    workspace_id=schedule.workspace_id,
                    content_id=schedule.content_id,
                    content_variant_id=variant,
                    schedule_id=schedule.id,
                    social_account_id=account.id if account else None,
                    platform=schedule.platform,
                    idempotency_key=key,
                    status=PublicationStatus.QUEUED,
                    scheduled_at=schedule.scheduled_at,
                )
                .on_conflict_do_nothing(index_elements=["idempotency_key"])
                .returning(Publication.id)
            )
        ).scalar_one_or_none()
        schedule.status = ScheduleStatus.DONE
        await db.execute(
            update(Content)
            .where(Content.id == schedule.content_id)
            .values(status=ContentStatus.PUBLISHING)
        )
        if pub_id is not None:
            await db.flush()
            pub = await db.get(Publication, pub_id)
            assert pub is not None
            if account is None:
                label = PLATFORM_LABEL.get(schedule.platform, schedule.platform.value)
                _fail(
                    pub,
                    "not_connected",
                    f"No {label} account is connected. Connect one in Social accounts, then retry.",
                )
                await _report(db, pub, await db.get(Content, pub.content_id))
            else:
                stats["queued"] += 1
                await db.commit()
                await queue.enqueue(
                    "publish_publication", publication_id=str(pub.id), _job_id=_job_id(pub)
                )
                continue
    await _refresh_content_statuses(db, {s.content_id for s in due} | {p.content_id for p in stuck})
    await db.commit()
    return stats


async def _account_for(db: AsyncSession, schedule: ContentSchedule) -> SocialAccount | None:
    q = select(SocialAccount).where(
        SocialAccount.workspace_id == schedule.workspace_id,
        SocialAccount.platform == schedule.platform,
        SocialAccount.deleted_at.is_(None),
        SocialAccount.status == SocialAccountStatus.CONNECTED,
    )
    if schedule.social_account_id:
        q = q.where(SocialAccount.id == schedule.social_account_id)
    return (await db.execute(q.order_by(SocialAccount.created_at).limit(1))).scalar_one_or_none()


async def _report(db: AsyncSession, pub: Publication, content: Content | None) -> None:
    """Activity log and notifications for a finished publication (same transaction)."""
    from app.agents import activity
    from app.models.enums import AgentKind, AgentRunStatus, NotificationType
    from app.notifications.service import notify

    label = PLATFORM_LABEL.get(pub.platform, pub.platform.value)
    title = content.title if content else "A post"
    url = f"/content/{pub.content_id}"
    ok = pub.status is PublicationStatus.PUBLISHED
    run = await activity.start(
        db, pub.workspace_id, AgentKind.PUBLISHING, f"Publish \u201c{title}\u201d to {label}"
    )
    await activity.step(
        db,
        run,
        f"Published to {label}" if ok else f"Couldn't publish to {label}",
        detail=pub.platform_url if ok else pub.error_message,
        status=AgentRunStatus.SUCCEEDED if ok else AgentRunStatus.FAILED,
    )
    activity.finish(
        run,
        AgentRunStatus.SUCCEEDED if ok else AgentRunStatus.FAILED,
        f"Live on {label}." if ok else (pub.error_message or "Publishing failed."),
        error=None if ok else pub.error_code,
    )
    if ok:
        await notify(
            db,
            workspace_id=pub.workspace_id,
            kind=NotificationType.POST_PUBLISHED,
            title=f"\u201c{title}\u201d is live on {label}",
            action_url=url,
            dedupe=f"published:{pub.id}",
            entity=("content", pub.content_id),
        )
    else:
        kind = (
            NotificationType.ACCOUNT_DISCONNECTED
            if pub.error_code == "needs_reauth"
            else NotificationType.POST_FAILED
        )
        await notify(
            db,
            workspace_id=pub.workspace_id,
            kind=NotificationType.POST_FAILED,
            title=f"\u201c{title}\u201d didn't publish to {label}",
            body=pub.error_message,
            action_url=url,
            dedupe=f"failed:{pub.id}:{pub.retry_count}",
            priority="high",
            entity=("content", pub.content_id),
        )
        if kind is NotificationType.ACCOUNT_DISCONNECTED:
            await notify(
                db,
                workspace_id=pub.workspace_id,
                kind=kind,
                title=f"Reconnect your {label} account",
                body="Its access expired or was removed, so posts can't go out there.",
                action_url="/settings/social",
                dedupe=f"reauth:{pub.social_account_id}:{utcnow().date()}",
                priority="high",
                roles=(WorkspaceRole.OWNER, WorkspaceRole.ADMIN),
            )


def _fail(pub: Publication, code: str, message: str) -> None:
    pub.status = PublicationStatus.FAILED
    pub.error_code = code
    pub.error_message = message[:2000]
    pub.next_retry_at = None


async def _refresh_content_statuses(db: AsyncSession, content_ids: set[uuid.UUID]) -> None:
    await db.flush()  # the session doesn't autoflush; read what we just changed
    for cid in content_ids:
        statuses = (
            (await db.execute(select(Publication.status).where(Publication.content_id == cid)))
            .scalars()
            .all()
        )
        pending_schedules = (
            await db.execute(
                select(ContentSchedule.id)
                .where(
                    ContentSchedule.content_id == cid,
                    ContentSchedule.status == ScheduleStatus.QUEUED,
                )
                .limit(1)
            )
        ).first()
        if not statuses:
            continue
        if pending_schedules or any(
            s in (PublicationStatus.QUEUED, PublicationStatus.PUBLISHING) for s in statuses
        ):
            new = ContentStatus.PUBLISHING
        elif all(s is PublicationStatus.PUBLISHED for s in statuses):
            new = ContentStatus.PUBLISHED
        else:
            new = ContentStatus.FAILED
        await db.execute(update(Content).where(Content.id == cid).values(status=new))


def _absolute(url: str) -> str:
    return url if url.startswith("http") else f"{settings.APP_URL.rstrip('/')}{url}"


def _stream(asset: MediaAsset):  # type: ignore[no-untyped-def]
    def open_() -> AsyncIterator[bytes]:
        return get_storage().stream(asset.storage_key)

    return open_


async def _request(db: AsyncSession, pub: Publication, content: Content) -> PublishRequest:
    variant = (
        await db.get(ContentVariant, pub.content_variant_id) if pub.content_variant_id else None
    )
    caption = (variant.caption if variant else content.caption) or ""
    cta = variant.cta if variant else content.cta
    if cta and cta not in caption:
        caption = f"{caption}\n\n{cta}".strip()
    tags = list(variant.hashtags if variant else content.hashtags or [])
    if tags:
        caption = f"{caption}\n\n" + " ".join(f"#{t}" for t in tags)
    assets = (
        (
            await db.execute(
                select(MediaAsset)
                .join(ContentMedia, ContentMedia.media_asset_id == MediaAsset.id)
                .where(
                    ContentMedia.content_id == content.id,
                    MediaAsset.deleted_at.is_(None),
                    MediaAsset.status == MediaStatus.READY,
                )
                .order_by(ContentMedia.position)
            )
        )
        .scalars()
        .all()
    )
    storage = get_storage()
    media = [
        MediaItem(
            kind="video" if a.kind is MediaKind.VIDEO else "image",
            url=_absolute(storage.download_url(a.storage_key)),
            mime_type=a.mime_type,
            size_bytes=a.size_bytes,
            duration_seconds=float(a.duration_seconds) if a.duration_seconds else None,
            width=a.width,
            height=a.height,
            open=_stream(a),
        )
        for a in assets
    ]
    return PublishRequest(
        platform=pub.platform,
        content_type=content.content_type,
        title=content.title,
        caption=caption,
        media=media,
    )


async def publish(
    db: AsyncSession, queue: JobQueue, publication_id: uuid.UUID
) -> PublicationStatus | None:
    pub = (
        await db.execute(
            select(Publication)
            .where(Publication.id == publication_id)
            .with_for_update(skip_locked=True)
        )
    ).scalar_one_or_none()
    if pub is None or pub.status is not PublicationStatus.QUEUED:
        return pub.status if pub else None  # already handled, being handled, or cancelled
    content = await db.get(Content, pub.content_id)
    account = await db.get(SocialAccount, pub.social_account_id) if pub.social_account_id else None
    adapter = registry.for_platform(pub.platform)
    if content is None or content.deleted_at is not None:
        pub.status = PublicationStatus.CANCELLED
        await db.commit()
        return pub.status
    if (
        account is None
        or account.deleted_at is not None
        or account.status is not SocialAccountStatus.CONNECTED
        or adapter is None
    ):
        _fail(
            pub,
            "not_connected",
            "The account isn't connected anymore. Reconnect it in Social accounts, then retry.",
        )
        await _refresh_content_statuses(db, {content.id})
        if pub.status in (PublicationStatus.FAILED, PublicationStatus.PUBLISHED):
            await _report(db, pub, content)
        await db.commit()
        return pub.status

    req = await _request(db, pub, content)
    problems = adapter.validate(req)
    if problems:
        _fail(pub, "invalid_post", " ".join(problems))
        await _refresh_content_statuses(db, {content.id})
        if pub.status in (PublicationStatus.FAILED, PublicationStatus.PUBLISHED):
            await _report(db, pub, content)
        await db.commit()
        return pub.status
    tokens = await token_row(db, account.id)
    if tokens is None:
        await mark_needs_reauth(db, account, "Access is missing. Reconnect the account.")
        _fail(pub, "not_connected", "The account needs to be reconnected.")
        await db.commit()
        return pub.status

    try:
        credentials = token_set(tokens)
    except InvalidToken:
        await mark_needs_reauth(
            db, account, "Stored access couldn't be read. Reconnect the account."
        )
        _fail(pub, "needs_reauth", "The account needs to be reconnected.")
        await _refresh_content_statuses(db, {content.id})
        if pub.status in (PublicationStatus.FAILED, PublicationStatus.PUBLISHED):
            await _report(db, pub, content)
        await db.commit()
        return pub.status

    # Point of no return: record the attempt before calling the platform.
    pub.status = PublicationStatus.PUBLISHING
    pub.last_attempt_at = utcnow()
    state: dict[str, Any] = dict(pub.provider_state or {})
    await db.commit()

    try:
        result = await adapter.publish(account.external_account_id, credentials, req, state)
    except SocialError as exc:
        pub.provider_state = state
        if exc.needs_reauth:
            await mark_needs_reauth(db, account, str(exc))
            _fail(pub, "needs_reauth", str(exc))
        elif exc.processing and state.get("polls", 0) < MAX_PROCESSING_POLLS:
            pub.provider_state = {**state, "polls": state.get("polls", 0) + 1}
            pub.status = PublicationStatus.QUEUED
            pub.next_retry_at = utcnow() + timedelta(seconds=PROCESSING_POLL_SECONDS)
        elif exc.retryable and pub.retry_count < len(BACKOFF_SECONDS):
            delay = BACKOFF_SECONDS[pub.retry_count]
            pub.retry_count += 1
            pub.status = PublicationStatus.QUEUED
            pub.error_code, pub.error_message = exc.code, str(exc)[:2000]
            pub.next_retry_at = utcnow() + timedelta(seconds=delay)
        else:
            _fail(pub, exc.code, str(exc))
        await _refresh_content_statuses(db, {content.id})
        if pub.status is PublicationStatus.FAILED:
            await _report(db, pub, content)
        await db.commit()
        if pub.status is PublicationStatus.QUEUED and pub.next_retry_at:
            delay = max(1, int((pub.next_retry_at - utcnow()).total_seconds()))
            await queue.enqueue(
                "publish_publication",
                publication_id=str(pub.id),
                _defer_by=delay,
                _job_id=_job_id(pub),
            )
        return pub.status
    except Exception:
        # Unexpected crash after we may have reached the platform: leave it `publishing`;
        # the sweep reports an unknown outcome instead of retrying blindly.
        log.exception("publish crashed for %s", pub.id)
        raise

    pub.status = PublicationStatus.PUBLISHED
    pub.platform_post_id = result.post_id
    pub.platform_url = result.url
    pub.published_at = utcnow()
    pub.error_code = pub.error_message = None
    pub.next_retry_at = None
    pub.provider_state = {**state, **({"result": result.details} if result.details else {})}
    account.last_error = None
    await _refresh_content_statuses(db, {content.id})
    await _report(db, pub, content)
    audit.record(
        db,
        "content.published",
        workspace_id=pub.workspace_id,
        data={
            "content_id": str(content.id),
            "platform": pub.platform.value,
            "post_id": result.post_id,
        },
    )
    await db.commit()
    return pub.status


async def retry(
    db: AsyncSession, queue: JobQueue, workspace_id: uuid.UUID, publication_id: uuid.UUID
) -> Publication:
    """Manual retry after a failure (including an unknown outcome the user has checked)."""
    from app.core.errors import AppError, not_found

    pub = (
        await db.execute(
            select(Publication)
            .where(and_(Publication.id == publication_id, Publication.workspace_id == workspace_id))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if pub is None:
        raise not_found("Publication")
    if pub.status is not PublicationStatus.FAILED:
        raise AppError(409, "not_failed", "Only failed posts can be retried.")
    label = PLATFORM_LABEL.get(pub.platform, pub.platform.value)
    if pub.social_account_id:
        # Retry on the same account it was meant for, never quietly on a different one.
        account = await db.get(SocialAccount, pub.social_account_id)
        if (
            account is None
            or account.deleted_at is not None
            or account.status is not SocialAccountStatus.CONNECTED
        ):
            name = f" {account.display_name}" if account and account.display_name else ""
            raise AppError(409, "not_connected", f"Reconnect the {label} account{name} first.")
    else:
        schedule = await db.get(ContentSchedule, pub.schedule_id) if pub.schedule_id else None
        account = await _account_for(db, schedule) if schedule else None
        if account is None:
            raise AppError(409, "not_connected", f"Connect a {label} account first.")
    pub.social_account_id = account.id
    pub.status = PublicationStatus.QUEUED
    pub.retry_count = 0
    pub.error_code = pub.error_message = None
    if pub.provider_state.get("polls"):
        pub.provider_state = {k: v for k, v in pub.provider_state.items() if k != "polls"}
    await _refresh_content_statuses(db, {pub.content_id})
    await db.commit()
    await queue.enqueue(
        "publish_publication",
        publication_id=str(pub.id),
        _job_id=f"{_job_id(pub)}:manual:{int(utcnow().timestamp())}",
    )
    return pub
