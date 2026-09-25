from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.media.processing import process_asset
from app.models import User, WorkspaceMember
from app.models.enums import WorkspaceRole
from app.storage import get_storage
from app.storage.local import make_token
from app.workers.jobs.media import delete_media_objects
from app.workers.queue import RecordingJobQueue
from tests.conftest import register_verified
from tests.media_helpers import png_bytes, upload


async def _ws(client: httpx.AsyncClient) -> str:
    return (await client.get("/workspaces")).json()[0]["id"]


async def test_upload_process_and_serve_image(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "media@example.com")
    ws = await _ws(client)
    data = png_bytes()
    pending = await upload(client, ws, data, process=False)
    assert pending["status"] == "processing"
    assert queue.last("process_media")["asset_id"] == pending["id"]

    async with SessionLocal() as db:
        await process_asset(db, get_storage(), uuid.UUID(pending["id"]))
    asset = (await client.get(f"/workspaces/{ws}/media/{pending['id']}")).json()
    assert asset["status"] == "ready"
    assert (asset["width"], asset["height"]) == (1200, 800)
    assert asset["display_name"] == "latte art"
    assert asset["kind"] == "image" and asset["size_bytes"] == len(data)

    original = await client.get(f"http://testserver{asset['url']}")
    assert original.status_code == 200 and original.content == data
    assert original.headers["content-type"] == "image/png"
    assert "sandbox" in original.headers["content-security-policy"]
    thumb = await client.get(f"http://testserver{asset['thumbnail_url']}")
    assert thumb.headers["content-type"] == "image/webp" and len(thumb.content) < len(data)

    page = (await client.get(f"/workspaces/{ws}/media")).json()
    assert page["total"] == 1 and page["items"][0]["id"] == asset["id"]


async def test_rejects_unsupported_and_oversized(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "reject@example.com")
    ws = await _ws(client)
    r = await client.post(
        f"/workspaces/{ws}/media/uploads",
        json={"filename": "logo.svg", "content_type": "image/svg+xml", "size_bytes": 100},
    )
    assert r.status_code == 415
    r = await client.post(
        f"/workspaces/{ws}/media/uploads",
        json={"filename": "huge.jpg", "content_type": "image/jpeg", "size_bytes": 26 * 1024 * 1024},
    )
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


async def test_spoofed_file_is_quarantined(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "spoof@example.com")
    ws = await _ws(client)
    asset = await upload(client, ws, b"<html><script>alert(1)</script></html>", filename="cat.png")
    assert asset["status"] == "quarantined"
    assert asset["url"] is None and "don't match" in asset["error"]


async def test_upload_link_is_a_narrow_capability(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "cap@example.com")
    ws = await _ws(client)
    r = await client.post(
        f"/workspaces/{ws}/media/uploads",
        json={"filename": "a.png", "content_type": "image/png", "size_bytes": 10},
    )
    url = "http://testserver" + r.json()["upload"]["url"]
    # Tampered token
    assert (
        await client.put(url[:-3] + "xyz", content=b"x", headers={"content-type": "image/png"})
    ).status_code == 403
    # Different content type than granted
    assert (
        await client.put(url, content=b"x", headers={"content-type": "text/html"})
    ).status_code == 400
    # Larger than the grant allows, even without a Content-Length header
    token = make_token(
        {
            "a": "put",
            "k": "workspaces/x/y.png",
            "ct": "image/png",
            "max": 8,
            "exp": time.time() + 60,
        }
    )

    async def body():  # type: ignore[no-untyped-def]
        yield b"0123456789abcdef"

    r = await client.put(
        f"http://testserver/api/v1/storage/local/upload?token={token}",
        content=body(),
        headers={"content-type": "image/png"},
    )
    assert r.status_code == 413
    # Expired download link
    expired = make_token({"a": "get", "k": "workspaces/x/y.png", "exp": time.time() - 1})
    assert (
        await client.get(f"http://testserver/api/v1/storage/local/object?token={expired}")
    ).status_code == 403


async def test_other_workspaces_cannot_see_or_touch_media(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    make_client,  # type: ignore[no-untyped-def]
) -> None:
    await register_verified(client, queue, "owner-m@example.com")
    ws = await _ws(client)
    asset = await upload(client, ws, png_bytes())
    other = await make_client()
    await register_verified(other, queue, "other-m@example.com")
    assert (await other.get(f"/workspaces/{ws}/media/{asset['id']}")).status_code == 404
    other_ws = await _ws(other)
    # Asset ID from workspace A used through workspace B
    assert (await other.get(f"/workspaces/{other_ws}/media/{asset['id']}")).status_code == 404
    assert (await other.delete(f"/workspaces/{other_ws}/media/{asset['id']}")).status_code == 404
    assert (
        await other.post(f"/workspaces/{other_ws}/media/{asset['id']}/complete")
    ).status_code == 404


async def test_viewer_can_browse_but_not_upload(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    make_client,  # type: ignore[no-untyped-def]
) -> None:
    await register_verified(client, queue, "own-v@example.com")
    ws = await _ws(client)
    viewer = await make_client()
    await register_verified(viewer, queue, "view-v@example.com")
    async with SessionLocal() as db:
        v = (await db.execute(select(User).where(User.email == "view-v@example.com"))).scalar_one()
        db.add(WorkspaceMember(workspace_id=uuid.UUID(ws), user_id=v.id, role=WorkspaceRole.VIEWER))
        await db.commit()
    assert (await viewer.get(f"/workspaces/{ws}/media")).status_code == 200
    r = await viewer.post(
        f"/workspaces/{ws}/media/uploads",
        json={"filename": "a.png", "content_type": "image/png", "size_bytes": 10},
    )
    assert r.status_code == 403


async def test_duplicates_are_flagged(client: httpx.AsyncClient, queue: RecordingJobQueue) -> None:
    await register_verified(client, queue, "dup@example.com")
    ws = await _ws(client)
    data = png_bytes((200, 120, 40))
    first = await upload(client, ws, data, filename="espresso.png")
    second = await upload(client, ws, data, filename="espresso copy.png")
    assert first["duplicate_of"] is None
    assert second["duplicate_of"] == first["id"]


async def test_tags_search_folders_and_delete(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    storage,  # type: ignore[no-untyped-def]
) -> None:
    await register_verified(client, queue, "org@example.com")
    ws = await _ws(client)
    a = await upload(client, ws, png_bytes((1, 2, 3)), filename="cold-brew.png")
    b = await upload(client, ws, png_bytes((4, 5, 6)), filename="croissant.png")

    r = await client.patch(
        f"/workspaces/{ws}/media/{a['id']}",
        json={
            "tags": ["#Cold Brew", "summer", "summer", "  "],
            "description": "Our 18-hour cold brew",
        },
    )
    assert r.json()["tags"] == ["cold brew", "summer"]
    await client.patch(f"/workspaces/{ws}/media/{b['id']}", json={"tags": ["pastry", "summer"]})

    tags = (await client.get(f"/workspaces/{ws}/media/tags")).json()
    assert tags[0] == {"tag": "summer", "count": 2}
    assert [
        i["id"] for i in (await client.get(f"/workspaces/{ws}/media?tag=pastry")).json()["items"]
    ] == [b["id"]]
    assert [
        i["id"] for i in (await client.get(f"/workspaces/{ws}/media?q=18-hour")).json()["items"]
    ] == [a["id"]]
    assert (await client.get(f"/workspaces/{ws}/media?q=100%25")).json()[
        "total"
    ] == 0  # LIKE wildcards escaped

    folder = (await client.post(f"/workspaces/{ws}/media-folders", json={"name": "Drinks"})).json()
    assert (
        await client.post(f"/workspaces/{ws}/media-folders", json={"name": "drinks"})
    ).status_code == 409
    await client.patch(f"/workspaces/{ws}/media/{a['id']}", json={"folder_id": folder["id"]})
    listed = (await client.get(f"/workspaces/{ws}/media-folders")).json()
    assert listed == [{"id": folder["id"], "name": "Drinks", "asset_count": 1}]
    assert (await client.get(f"/workspaces/{ws}/media?folder={folder['id']}")).json()["total"] == 1
    assert (await client.get(f"/workspaces/{ws}/media?folder=unfiled")).json()["total"] == 1
    assert (
        await client.delete(f"/workspaces/{ws}/media-folders/{folder['id']}")
    ).status_code == 204
    assert (await client.get(f"/workspaces/{ws}/media?folder=unfiled")).json()[
        "total"
    ] == 2  # files kept

    # Pagination is stable and complete
    first = (await client.get(f"/workspaces/{ws}/media?limit=1")).json()
    second = (
        await client.get(f"/workspaces/{ws}/media?limit=1&cursor={first['next_cursor']}")
    ).json()
    assert {first["items"][0]["id"], second["items"][0]["id"]} == {a["id"], b["id"]}
    assert second["next_cursor"] is None

    assert (await client.delete(f"/workspaces/{ws}/media/{a['id']}")).status_code == 204
    assert (await client.get(f"/workspaces/{ws}/media/{a['id']}")).status_code == 404
    keys = queue.last("delete_media_objects")["keys"]
    assert len(keys) == 2  # original and thumbnail
    await delete_media_objects({}, keys)
    assert [await storage.head(k) for k in keys] == [None, None]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
async def test_video_duration_and_thumbnail(
    client: httpx.AsyncClient, queue: RecordingJobQueue, tmp_path: Path
) -> None:
    await register_verified(client, queue, "video@example.com")
    ws = await _ws(client)
    clip = tmp_path / "clip.mp4"
    argv = [shutil.which("ffmpeg") or "ffmpeg", "-v", "error", "-f", "lavfi"]
    argv += ["-i", "testsrc=size=320x568:rate=24", "-t", "2", "-pix_fmt", "yuv420p", str(clip)]
    await asyncio.to_thread(subprocess.run, argv, check=True)
    asset = await upload(
        client, ws, clip.read_bytes(), filename="pour.mp4", content_type="video/mp4"
    )
    assert asset["status"] == "ready" and asset["kind"] == "video"
    assert (asset["width"], asset["height"]) == (320, 568)
    assert 1.9 <= asset["duration_seconds"] <= 2.1
    assert asset["thumbnail_url"]
