"""Signed upload/download endpoints for STORAGE_PROVIDER=local.

The signed token is the capability (like a presigned S3 URL): it names one key, one action,
a content type and a size limit, and expires. These routes are CSRF-exempt for that reason.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.errors import AppError
from app.storage import get_storage
from app.storage.local import LocalStorage, read_token

router = APIRouter(prefix="/storage/local", tags=["storage"], include_in_schema=False)

INLINE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "video/mp4",
    "video/quicktime",
    "video/webm",
}


def _local() -> LocalStorage:
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise AppError(404, "not_found", "Not found.")
    return storage


@router.put("/upload", status_code=204)
async def upload(request: Request, token: str) -> Response:
    storage = _local()
    grant = read_token(token, "put")
    if grant is None:
        raise AppError(
            403, "upload_link_invalid", "This upload link has expired. Start the upload again."
        )
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type != grant["ct"]:
        raise AppError(400, "content_type_mismatch", "The file type doesn't match the upload.")
    declared = request.headers.get("content-length")
    if declared and int(declared) > int(grant["max"]):  # type: ignore[arg-type]
        raise AppError(413, "file_too_large", "The file is larger than allowed.")
    try:
        await storage.write_stream(
            str(grant["k"]), request.stream(), content_type, int(grant["max"])
        )  # type: ignore[arg-type]
    except OverflowError as exc:
        raise AppError(413, "file_too_large", "The file is larger than allowed.") from exc
    return Response(status_code=204)


@router.get("/object")
async def download(token: str) -> StreamingResponse:
    storage = _local()
    grant = read_token(token, "get")
    if grant is None:
        raise AppError(403, "link_expired", "This link has expired. Reload the page.")
    key = str(grant["k"])
    info = await storage.head(key)
    if info is None:
        raise AppError(404, "not_found", "File not found.")
    content_type = info.content_type or "application/octet-stream"
    inline = content_type in INLINE_TYPES and "fn" not in grant
    headers = {
        "Content-Length": str(info.size_bytes),
        "Cache-Control": f"private, max-age={min(settings.STORAGE_URL_TTL_SECONDS, 3600)}",
        "Content-Disposition": "inline"
        if inline
        else f'attachment; filename="{grant.get("fn", "file")}"',
        # Even if a file were mislabelled, never let it run scripts on our origin.
        "Content-Security-Policy": "default-src 'none'; img-src 'self'; media-src 'self'; sandbox",
    }
    return StreamingResponse(
        storage.stream(key),
        media_type=content_type if inline else "application/octet-stream",
        headers=headers,
    )
