"""Object storage abstraction. Bytes never pass through PostgreSQL.

Uploads go straight from the browser to storage (presigned POST on S3, a signed capability URL
for local disk), so the API never buffers large files in memory.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class UploadTarget:
    """How the browser should send the file. `fields` are form fields for a multipart POST
    (S3); for a PUT the file is the raw body and `headers` must be sent."""

    url: str
    method: str  # "POST" (multipart form, file field last) or "PUT" (raw body)
    fields: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ObjectInfo:
    size_bytes: int
    content_type: str | None


class Storage(Protocol):
    name: str
    bucket: str

    def upload_target(self, key: str, content_type: str, max_bytes: int) -> UploadTarget: ...

    def download_url(self, key: str, *, filename: str | None = None) -> str: ...

    async def head(self, key: str) -> ObjectInfo | None: ...

    def stream(self, key: str, chunk_size: int = 1 << 20) -> AsyncIterator[bytes]: ...

    async def read_prefix(self, key: str, length: int) -> bytes: ...

    async def download_to(self, key: str, path: str) -> None: ...

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def delete(self, key: str) -> None: ...
