from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import shutil
import time
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote

from app.core.config import settings
from app.storage.base import ObjectInfo, UploadTarget

_PURPOSE = b"storage-local-v1"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def make_token(payload: dict[str, object]) -> str:
    """Capability token: whoever holds it may do exactly `payload` until `exp`."""
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    sig = hmac.new(settings.SESSION_SECRET.encode(), _PURPOSE + body.encode(), hashlib.sha256)
    return f"{body}.{_b64(sig.digest())}"


def read_token(token: str, action: str) -> dict[str, object] | None:
    body, _, sig = token.partition(".")
    if not body or not sig:
        return None
    expected = hmac.new(settings.SESSION_SECRET.encode(), _PURPOSE + body.encode(), hashlib.sha256)
    try:
        if not hmac.compare_digest(_unb64(sig), expected.digest()):
            return None
        payload = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("a") != action or float(payload.get("exp", 0)) < time.time():
        return None
    return payload


class LocalStorage:
    """Files on local disk, served through signed URLs on the API. Development and tests."""

    name = "local"

    def __init__(self, root: str | Path, bucket: str = "local") -> None:
        self.root = Path(root).resolve()
        self.bucket = bucket
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    def upload_target(self, key: str, content_type: str, max_bytes: int) -> UploadTarget:
        token = make_token(
            {"a": "put", "k": key, "ct": content_type, "max": max_bytes, "exp": time.time() + 900}
        )
        return UploadTarget(
            url=f"{settings.API_PREFIX}/storage/local/upload?token={token}",
            method="PUT",
            headers={"content-type": content_type},
        )

    def download_url(self, key: str, *, filename: str | None = None) -> str:
        # Expiry is bucketed so the same file keeps the same URL for a while and browsers can
        # cache it; every URL is valid for at least one full TTL.
        ttl = settings.STORAGE_URL_TTL_SECONDS
        payload: dict[str, object] = {
            "a": "get",
            "k": key,
            "exp": (int(time.time()) // ttl + 2) * ttl,
        }
        if filename:
            payload["fn"] = filename
        return f"{settings.API_PREFIX}/storage/local/object?token={quote(make_token(payload))}"

    async def head(self, key: str) -> ObjectInfo | None:
        path = self._path(key)
        if not path.is_file():
            return None
        meta = path.with_name(path.name + ".ct")
        ct = meta.read_text() if meta.exists() else None
        return ObjectInfo(size_bytes=path.stat().st_size, content_type=ct)

    async def stream(self, key: str, chunk_size: int = 1 << 20) -> AsyncIterator[bytes]:
        path = self._path(key)
        with path.open("rb") as fh:
            while chunk := await asyncio.to_thread(fh.read, chunk_size):
                yield chunk

    async def read_prefix(self, key: str, length: int) -> bytes:
        with self._path(key).open("rb") as fh:
            return fh.read(length)

    async def download_to(self, key: str, path: str) -> None:
        await asyncio.to_thread(shutil.copyfile, self._path(key), path)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        await asyncio.to_thread(tmp.write_bytes, data)
        os.replace(tmp, path)
        path.with_name(path.name + ".ct").write_text(content_type)

    async def write_stream(
        self, key: str, chunks: AsyncIterator[bytes], content_type: str, max_bytes: int
    ) -> int:
        """Stream a request body to disk, aborting as soon as it exceeds `max_bytes`."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        written = 0
        try:
            with tmp.open("wb") as fh:
                async for chunk in chunks:
                    written += len(chunk)
                    if written > max_bytes:
                        raise OverflowError
                    fh.write(chunk)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        os.replace(tmp, path)
        path.with_name(path.name + ".ct").write_text(content_type)
        return written

    async def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)
        path.with_name(path.name + ".ct").unlink(missing_ok=True)
