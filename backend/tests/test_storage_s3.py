"""S3Storage against moto's in-process S3 (no network)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws

from app.storage.s3 import S3Storage


@pytest.fixture
def s3():  # type: ignore[no-untyped-def]
    with mock_aws():
        client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="x",
            aws_secret_access_key="y",
            config=Config(signature_version="s3v4"),
        )
        client.create_bucket(Bucket="cf-test")
        yield S3Storage(client=client, bucket="cf-test")


def test_presigned_post_enforces_type_and_size(s3: S3Storage) -> None:
    target = s3.upload_target("workspaces/w/media/a/photo.jpg", "image/jpeg", 1024)
    assert target.method == "POST"
    assert target.fields["key"] == "workspaces/w/media/a/photo.jpg"
    assert target.fields["Content-Type"] == "image/jpeg"
    assert "policy" in target.fields  # the signed policy carries content-length-range


def test_roundtrip(s3: S3Storage, tmp_path: Path) -> None:
    async def run() -> None:
        key = "workspaces/w/media/a/thumb.webp"
        assert await s3.head(key) is None
        await s3.put(key, b"RIFF....WEBP", "image/webp")
        info = await s3.head(key)
        assert info is not None and info.size_bytes == 12 and info.content_type == "image/webp"
        assert await s3.read_prefix(key, 4) == b"RIFF"
        await s3.download_to(key, str(tmp_path / "f"))
        assert (tmp_path / "f").read_bytes() == b"RIFF....WEBP"
        chunks = [c async for c in s3.stream(key, chunk_size=5)]
        assert b"".join(chunks) == b"RIFF....WEBP"
        assert "X-Amz-Signature" in s3.download_url(key)
        assert "response-content-disposition" in s3.download_url(key, filename="thumb.webp")
        await s3.delete(key)
        assert await s3.head(key) is None

    asyncio.run(run())


def test_presigned_put_for_r2(s3: S3Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    from app.core.config import settings

    monkeypatch.setattr(settings, "STORAGE_UPLOAD_METHOD", "put")
    key = "workspaces/w/media/b/photo.png"
    target = s3.upload_target(key, "image/png", 1024)
    assert target.method == "PUT" and target.fields == {}
    assert target.headers == {"Content-Type": "image/png"}
    assert "X-Amz-Signature" in target.url and "content-type" in target.url.lower()
    r = requests.put(target.url, data=b"\x89PNG....", headers=target.headers, timeout=5)
    assert r.status_code == 200

    async def check() -> None:
        info = await s3.head(key)
        assert info is not None and info.size_bytes == 8 and info.content_type == "image/png"

    asyncio.run(check())
