"""Post-upload processing (worker): verify bytes, checksum, dimensions, thumbnail, duplicates."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.policy import compatible, sniff
from app.models import MediaAsset
from app.models.enums import MediaKind, MediaStatus
from app.storage import Storage

log = logging.getLogger(__name__)

THUMB_EDGE = 640
Image.MAX_IMAGE_PIXELS = 80_000_000  # decompression-bomb guard (~80 MP)


def thumbnail_key(storage_key: str) -> str:
    return storage_key.rsplit("/", 1)[0] + "/thumb.webp"


def _image_meta(path: Path) -> tuple[int, int, bytes]:
    with Image.open(path) as im:
        im.verify()  # structural check; invalidates `im`
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        width, height = im.size
        im.thumbnail((THUMB_EDGE, THUMB_EDGE))
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        out = tempfile.SpooledTemporaryFile()
        im.save(out, "WEBP", quality=82, method=4)  # re-encoding also drops EXIF (e.g. GPS)
        out.seek(0)
        return width, height, out.read()


def _run(argv: list[str], timeout: int) -> subprocess.CompletedProcess[bytes]:
    # Absolute executable path, fixed argv, no shell: nothing user-controlled is interpreted.
    return subprocess.run(argv, capture_output=True, timeout=timeout, check=False)  # noqa: S603


def _video_meta(path: Path) -> tuple[int | None, int | None, float | None, bytes | None]:
    """Uses ffprobe/ffmpeg when installed; otherwise metadata stays empty (still usable)."""
    ffprobe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not ffprobe:
        return None, None, None, None
    probe = _run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration", "-of", "json", str(path)],
        timeout=60,
    )  # fmt: skip
    if probe.returncode != 0:
        raise ValueError("The video file couldn't be read.")
    info = json.loads(probe.stdout or b"{}")
    stream = (info.get("streams") or [{}])[0]
    duration = info.get("format", {}).get("duration")
    thumb: bytes | None = None
    if ffmpeg:
        with tempfile.TemporaryDirectory() as tmp:
            frame = Path(tmp) / "frame.webp"
            scale = f"scale='min({THUMB_EDGE},iw)':-2"
            for seek in (["-ss", "1"], []):  # clips shorter than 1s: take the first frame
                argv = [ffmpeg, "-v", "error", *seek, "-i", str(path)]
                _run([*argv, "-frames:v", "1", "-vf", scale, str(frame)], timeout=120)
                if frame.exists():
                    thumb = frame.read_bytes()
                    break
    return stream.get("width"), stream.get("height"), float(duration) if duration else None, thumb


async def process_asset(
    db: AsyncSession, storage: Storage, asset_id: uuid.UUID
) -> MediaAsset | None:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.deleted_at is not None or asset.status is not MediaStatus.PROCESSING:
        return asset

    def fail(reason: str) -> None:
        asset.status = MediaStatus.FAILED
        asset.ai_metadata = {**asset.ai_metadata, "error": reason}

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "original"
        try:
            await storage.download_to(asset.storage_key, str(path))
        except Exception:
            log.exception("media download failed", extra={"asset_id": str(asset.id)})
            fail("The uploaded file couldn't be found in storage. Upload it again.")
            await db.commit()
            return asset

        with path.open("rb") as fh:
            head = fh.read(64)
        if not compatible(asset.mime_type, sniff(head)):
            asset.status = MediaStatus.QUARANTINED
            asset.ai_metadata = {
                **asset.ai_metadata,
                "error": "The file's contents don't match its type, so it wasn't added.",
            }
            await storage.delete(asset.storage_key)
            await db.commit()
            return asset

        sha = hashlib.sha256()
        with path.open("rb") as fh:
            while chunk := fh.read(1 << 20):
                sha.update(chunk)
        asset.checksum_sha256 = sha.hexdigest()
        asset.size_bytes = path.stat().st_size

        try:
            if asset.kind is MediaKind.IMAGE:
                w, h, thumb = await asyncio.to_thread(_image_meta, path)
                asset.width, asset.height = w, h
            else:
                w, h, duration, thumb = await asyncio.to_thread(_video_meta, path)
                asset.width, asset.height = w, h
                asset.duration_seconds = Decimal(str(round(duration, 3))) if duration else None
        except (
            OSError,
            ValueError,
            Image.DecompressionBombError,
            subprocess.TimeoutExpired,
        ) as exc:
            fail(str(exc) if isinstance(exc, ValueError) else "The file couldn't be read as media.")
            await db.commit()
            return asset

        if thumb:
            key = thumbnail_key(asset.storage_key)
            await storage.put(key, thumb, "image/webp")
            asset.thumbnail_key = key

    duplicate = (
        await db.execute(
            select(MediaAsset.id)
            .where(
                MediaAsset.workspace_id == asset.workspace_id,
                MediaAsset.checksum_sha256 == asset.checksum_sha256,
                MediaAsset.id != asset.id,
                MediaAsset.status == MediaStatus.READY,
                MediaAsset.deleted_at.is_(None),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    meta = {k: v for k, v in asset.ai_metadata.items() if k != "error"}
    if duplicate:
        meta["duplicate_of"] = str(duplicate)
    asset.ai_metadata = meta
    asset.status = MediaStatus.READY
    await db.commit()
    return asset
