"""Creating media: AI images, and videos assembled from the business's own photos and clips.

Both follow the allowance rules: reserve before work, commit on success, refund on failure.
An identical request (same provider, model, prompt or scene list) returns the existing asset
without charging again.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import usage as ai_usage
from app.ai.base import AIProviderError
from app.ai.images import ImageProvider
from app.core.config import settings
from app.core.errors import AppError, not_found
from app.media.policy import sniff
from app.media.processing import process_asset
from app.models import AIUsage, Brand, Content, ContentMedia, MediaAsset, User, Workspace
from app.models.enums import AIOperation, MediaKind, MediaSource, MediaStatus
from app.storage import Storage
from app.workers.queue import JobQueue

log = logging.getLogger("contentfactory.generation")
MAX_VIDEO_SECONDS = 90
SECONDS_PER_CREDIT = 30
VIDEO_SIZES = {"vertical": (1080, 1920), "square": (1080, 1080)}


def video_credits(total_seconds: float) -> int:
    return max(1, math.ceil(total_seconds / SECONDS_PER_CREDIT))


async def _reusable(db: AsyncSession, ws: Workspace, fingerprint: str) -> MediaAsset | None:
    return (
        await db.execute(
            select(MediaAsset)
            .where(
                MediaAsset.workspace_id == ws.id,
                MediaAsset.generation_fingerprint == fingerprint,
                MediaAsset.deleted_at.is_(None),
                MediaAsset.status.in_([MediaStatus.READY, MediaStatus.PROCESSING]),
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def _content(db: AsyncSession, ws: Workspace, content_id: uuid.UUID | None) -> Content | None:
    if content_id is None:
        return None
    c = await db.get(Content, content_id)
    if c is None or c.workspace_id != ws.id or c.deleted_at is not None:
        raise not_found("Post")
    return c


async def _attach(db: AsyncSession, content_id: str | None, asset: MediaAsset) -> None:
    """Add the new file to the post it was made for (first if the post has no media yet)."""
    if not content_id:
        return
    content = await db.get(Content, uuid.UUID(content_id))
    if content is None or content.deleted_at is not None:
        return
    exists = (
        await db.execute(
            select(ContentMedia.id).where(
                ContentMedia.content_id == content.id, ContentMedia.media_asset_id == asset.id
            )
        )
    ).first()
    if exists:
        return
    position = (
        await db.execute(
            select(func.coalesce(func.max(ContentMedia.position), -1)).where(
                ContentMedia.content_id == content.id
            )
        )
    ).scalar_one() + 1
    db.add(
        ContentMedia(
            content_id=content.id,
            media_asset_id=asset.id,
            position=position,
            role="primary" if position == 0 else "extra",
        )
    )


# ----------------------------------------------------------------------------- images
async def brand_prompt(db: AsyncSession, ws: Workspace, prompt: str, use_brand: bool) -> str:
    if not use_brand:
        return prompt.strip()
    brand = (
        await db.execute(select(Brand).where(Brand.workspace_id == ws.id))
    ).scalar_one_or_none()
    extras = []
    if brand and brand.visual_style:
        extras.append(f"Visual style: {brand.visual_style}")
    if brand and brand.colors:
        extras.append(f"Brand colours: {', '.join(brand.colors)}")
    extras.append("Photographic, natural light, no text or logos in the image")
    return f"{prompt.strip()}. " + ". ".join(extras) + "."


async def start_image(
    db: AsyncSession,
    ws: Workspace,
    user: User,
    *,
    prompt: str,
    aspect: str,
    use_brand: bool,
    content_id: uuid.UUID | None,
    queue: JobQueue,
    provider: ImageProvider,
    storage: Storage,
) -> tuple[MediaAsset, bool]:
    await _content(db, ws, content_id)
    final = await brand_prompt(db, ws, prompt, use_brand)
    fp = hashlib.sha256(
        json.dumps(["image", provider.name, provider.model, final, aspect]).encode()
    ).hexdigest()
    if (existing := await _reusable(db, ws, fp)) is not None:
        await _attach(db, str(content_id) if content_id else None, existing)
        await db.commit()
        return existing, True
    asset_id = uuid.uuid4()
    asset = MediaAsset(
        id=asset_id,
        workspace_id=ws.id,
        uploaded_by_id=user.id,
        kind=MediaKind.IMAGE,
        source=MediaSource.AI_GENERATED,
        status=MediaStatus.PROCESSING,
        storage_bucket=storage.bucket,
        storage_key=f"workspaces/{ws.id}/media/{asset_id}/generated",
        mime_type="image/png",
        size_bytes=0,
        display_name=prompt.strip()[:120] or "Generated image",
        alt_text=prompt.strip()[:2000],
        tags=["ai generated"],
        generation_fingerprint=fp,
        ai_metadata={
            "prompt": prompt,
            "final_prompt": final,
            "provider": provider.name,
            "model": provider.model,
            "aspect": aspect,
            "content_id": str(content_id) if content_id else None,
        },
    )
    db.add(asset)
    await db.flush()
    usage = await ai_usage.reserve(
        db,
        ws,
        user_id=user.id,
        operation=AIOperation.IMAGE,
        provider=provider.name,
        model=provider.model,
        fingerprint=fp,
        content_id=content_id,
    )
    await db.commit()
    await queue.enqueue("generate_image", asset_id=str(asset.id), usage_id=str(usage.id))
    return asset, False


async def run_image(
    db: AsyncSession,
    storage: Storage,
    provider: ImageProvider,
    asset_id: uuid.UUID,
    usage_id: uuid.UUID,
) -> MediaAsset | None:
    asset, usage = await db.get(MediaAsset, asset_id), await db.get(AIUsage, usage_id)
    if asset is None or usage is None or usage.status.value != "reserved":
        return asset
    meta = dict(asset.ai_metadata or {})
    try:
        image = await provider.generate(meta["final_prompt"], meta.get("aspect", "square"))
        mime = sniff(image.data[:64])
        if mime not in ("image/png", "image/jpeg", "image/webp"):
            raise AIProviderError("The image service returned an unreadable file.", retryable=False)
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[mime]
        asset.storage_key = f"{asset.storage_key.rsplit('/', 1)[0]}/generated.{ext}"
        asset.original_filename = f"generated.{ext}"
        asset.mime_type, asset.size_bytes = mime, len(image.data)
        await storage.put(asset.storage_key, image.data, mime)
        if image.revised_prompt:
            meta["revised_prompt"] = image.revised_prompt
        asset.ai_metadata = meta
        ai_usage.commit(usage, None)
        await db.commit()
    except AIProviderError as exc:
        await db.rollback()
        asset, usage = await db.get(MediaAsset, asset_id), await db.get(AIUsage, usage_id)
        assert asset is not None and usage is not None
        asset.status = MediaStatus.FAILED
        asset.ai_metadata = {**meta, "error": f"{exc} Your image allowance wasn't used."}
        ai_usage.refund(usage)
        await db.commit()
        return asset
    processed = await process_asset(db, storage, asset.id)  # verify, dimensions, thumbnail -> ready
    if processed and processed.status is MediaStatus.READY:
        await _attach(db, meta.get("content_id"), processed)
        await db.commit()
    return processed


# ----------------------------------------------------------------------------- video assembly
async def start_video(
    db: AsyncSession,
    ws: Workspace,
    user: User,
    *,
    scenes: list[dict[str, Any]],
    aspect: str,
    title: str | None,
    content_id: uuid.UUID | None,
    queue: JobQueue,
    storage: Storage,
) -> tuple[MediaAsset, bool]:
    if not shutil.which("ffmpeg"):
        raise AppError(
            503,
            "video_unavailable",
            "Video building isn't available on this server (ffmpeg is missing).",
        )
    await _content(db, ws, content_id)
    ids = [uuid.UUID(str(s["media_id"])) for s in scenes]
    found = {
        a.id: a
        for a in (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id.in_(ids),
                    MediaAsset.workspace_id == ws.id,
                    MediaAsset.deleted_at.is_(None),
                    MediaAsset.status == MediaStatus.READY,
                )
            )
        ).scalars()
    }
    if len(found) != len(set(ids)):
        raise AppError(
            422,
            "media_not_found",
            "One of the scenes uses a file that isn't ready in your library.",
        )
    if any(found[i].kind not in (MediaKind.IMAGE, MediaKind.VIDEO) for i in ids):
        raise AppError(422, "unsupported_scene", "Scenes can use photos and videos only.")
    total = sum(float(s["duration_s"]) for s in scenes)
    if total > MAX_VIDEO_SECONDS:
        raise AppError(
            422,
            "video_too_long",
            f"Videos can be up to {MAX_VIDEO_SECONDS} seconds. This one is {total:.0f}.",
        )
    plan = [
        {
            "media_id": str(s["media_id"]),
            "duration_s": round(float(s["duration_s"]), 2),
            "text": (s.get("text") or "").strip()[:120],
        }
        for s in scenes
    ]
    fp = hashlib.sha256(json.dumps(["video-assembly-v1", aspect, plan]).encode()).hexdigest()
    if (existing := await _reusable(db, ws, fp)) is not None:
        await _attach(db, str(content_id) if content_id else None, existing)
        await db.commit()
        return existing, True
    asset_id = uuid.uuid4()
    asset = MediaAsset(
        id=asset_id,
        workspace_id=ws.id,
        uploaded_by_id=user.id,
        kind=MediaKind.VIDEO,
        source=MediaSource.ASSEMBLED,
        status=MediaStatus.PROCESSING,
        storage_bucket=storage.bucket,
        storage_key=f"workspaces/{ws.id}/media/{asset_id}/video.mp4",
        mime_type="video/mp4",
        size_bytes=0,
        original_filename="video.mp4",
        display_name=(title or "New video")[:120],
        tags=["video"],
        generation_fingerprint=fp,
        ai_metadata={
            "scenes": plan,
            "aspect": aspect,
            "total_seconds": total,
            "content_id": str(content_id) if content_id else None,
        },
    )
    db.add(asset)
    await db.flush()
    usage = await ai_usage.reserve(
        db,
        ws,
        user_id=user.id,
        operation=AIOperation.VIDEO,
        provider="ffmpeg",
        model="assembly-v1",
        credits=video_credits(total),
        fingerprint=fp,
        content_id=content_id,
    )
    await db.commit()
    await queue.enqueue("render_video", asset_id=str(asset.id), usage_id=str(usage.id))
    return asset, False


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019").replace("%", "\\%")


def _font_arg(path: str | None) -> str | None:
    """ffmpeg filter syntax: forward slashes, and the drive colon escaped (C\\:/Windows/...)."""
    return path.replace("\\", "/").replace(":", "\\:") if path else None


def _render(
    workdir: Path, inputs: list[tuple[Path, str, float, str]], size: tuple[int, int], out: Path
) -> None:
    """One normalised segment per scene, then a lossless concat. Silent AAC track included,
    since some platforms reject videos without audio."""
    w, h = size
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    font = _font_arg(settings.video_font_path)
    segments = []
    for i, (src, kind, duration, text) in enumerate(inputs):
        # A clip shorter than its scene holds its last frame, so the video matches the plan.
        hold = [f"tpad=stop_mode=clone:stop_duration={duration}"] if kind == "video" else []
        vf = [
            *hold,
            f"scale={w}:{h}:force_original_aspect_ratio=decrease",
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
            "setsar=1",
            "fps=30",
            "format=yuv420p",
        ]
        if text and font:
            vf.append(
                f"drawtext=fontfile='{font}':text='{_escape(text)}':fontcolor=white:"
                f"fontsize={int(h * 0.035)}:"
                f"box=1:boxcolor=black@0.55:boxborderw=24:x=(w-text_w)/2:y=h*0.72"
            )
        seg = workdir / f"seg{i}.mp4"
        src_args = (
            ["-loop", "1", "-t", str(duration), "-i", str(src)]
            if kind == "image"
            else ["-t", str(duration), "-i", str(src)]
        )
        argv = [
            ffmpeg,
            "-v",
            "error",
            "-y",
            *src_args,
            "-f",
            "lavfi",
            "-t",
            str(duration),
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            ",".join(vf),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-shortest",
            str(seg),
        ]
        result = subprocess.run(argv, capture_output=True, timeout=300, check=False)  # noqa: S603 - fixed argv
        if result.returncode != 0:
            raise ValueError(f"Scene {i + 1} couldn't be processed.")
        segments.append(seg)
    listing = workdir / "list.txt"
    listing.write_text("".join(f"file '{s.name}'\n" for s in segments))
    argv = [
        ffmpeg,
        "-v",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(out),
    ]
    result = subprocess.run(argv, capture_output=True, timeout=300, check=False, cwd=workdir)  # noqa: S603
    if result.returncode != 0:
        raise ValueError("The scenes couldn't be joined.")


async def run_video(
    db: AsyncSession, storage: Storage, asset_id: uuid.UUID, usage_id: uuid.UUID
) -> MediaAsset | None:
    asset, usage = await db.get(MediaAsset, asset_id), await db.get(AIUsage, usage_id)
    if asset is None or usage is None or usage.status.value != "reserved":
        return asset
    meta = dict(asset.ai_metadata or {})
    try:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            inputs = []
            for i, scene in enumerate(meta["scenes"]):
                src = await db.get(MediaAsset, uuid.UUID(scene["media_id"]))
                if src is None or src.deleted_at is not None:
                    raise ValueError(f"Scene {i + 1}'s file was deleted.")
                path = workdir / f"in{i}"
                await storage.download_to(src.storage_key, str(path))
                inputs.append(
                    (path, src.kind.value, float(scene["duration_s"]), scene.get("text") or "")
                )
            out = workdir / "video.mp4"
            await asyncio.to_thread(
                _render,
                workdir,
                inputs,
                VIDEO_SIZES.get(meta.get("aspect", "vertical"), VIDEO_SIZES["vertical"]),
                out,
            )
            data = out.read_bytes()
        await storage.put(asset.storage_key, data, "video/mp4")
        asset.size_bytes = len(data)
        ai_usage.commit(usage, None)
        await db.commit()
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        await db.rollback()
        asset, usage = await db.get(MediaAsset, asset_id), await db.get(AIUsage, usage_id)
        assert asset is not None and usage is not None
        log.warning("video render failed for %s: %s", asset_id, exc)
        asset.status = MediaStatus.FAILED
        reason = str(exc) if isinstance(exc, ValueError) else "The video couldn't be built."
        asset.ai_metadata = {**meta, "error": f"{reason} Your video credits weren't used."}
        ai_usage.refund(usage)
        await db.commit()
        return asset
    processed = await process_asset(db, storage, asset.id)  # duration, dimensions, poster frame
    if processed and processed.status is MediaStatus.READY:
        await _attach(db, meta.get("content_id"), processed)
        await db.commit()
    return processed
