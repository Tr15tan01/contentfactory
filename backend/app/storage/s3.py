from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings
from app.storage.base import ObjectInfo, UploadTarget


class S3Storage:
    """Any S3-compatible service (AWS S3, MinIO, Cloudflare R2 with STORAGE_UPLOAD_METHOD=put).

    boto3 is synchronous; calls that hit the network run in a thread. Presigning is local.
    The bucket needs a CORS rule allowing POST/PUT from APP_URL (see docs/media-storage.md).
    """

    name = "s3"

    def __init__(self, client: Any | None = None, bucket: str | None = None) -> None:
        self.bucket = bucket or settings.STORAGE_BUCKET
        self._client = client or boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT or None,
            region_name=settings.STORAGE_REGION,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY or None,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY or None,
            config=Config(
                signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}
            ),
        )

    def upload_target(self, key: str, content_type: str, max_bytes: int) -> UploadTarget:
        if settings.STORAGE_UPLOAD_METHOD == "put":
            # Content-Type is signed, so the browser must send exactly this type. The size is
            # checked in complete_upload (HEAD), which deletes anything over the limit.
            url = self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=900,
            )
            return UploadTarget(url=url, method="PUT", headers={"Content-Type": content_type})
        # Presigned POST lets S3 itself enforce the size limit and exact content type.
        post = self._client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
            ExpiresIn=900,
        )
        return UploadTarget(url=post["url"], method="POST", fields=post["fields"])

    def download_url(self, key: str, *, filename: str | None = None) -> str:
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return str(
            self._client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=settings.STORAGE_URL_TTL_SECONDS
            )
        )

    async def head(self, key: str) -> ObjectInfo | None:
        try:
            r = await asyncio.to_thread(self._client.head_object, Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return ObjectInfo(size_bytes=int(r["ContentLength"]), content_type=r.get("ContentType"))

    async def stream(self, key: str, chunk_size: int = 1 << 20) -> AsyncIterator[bytes]:
        r = await asyncio.to_thread(self._client.get_object, Bucket=self.bucket, Key=key)
        body = r["Body"]
        while chunk := await asyncio.to_thread(body.read, chunk_size):
            yield chunk

    async def read_prefix(self, key: str, length: int) -> bytes:
        r = await asyncio.to_thread(
            self._client.get_object, Bucket=self.bucket, Key=key, Range=f"bytes=0-{length - 1}"
        )
        return bytes(await asyncio.to_thread(r["Body"].read))

    async def download_to(self, key: str, path: str) -> None:
        await asyncio.to_thread(self._client.download_file, self.bucket, key, path)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self.bucket, Key=key)
