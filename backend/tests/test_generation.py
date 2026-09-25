from __future__ import annotations

import asyncio
import base64
import io
import json
import shutil
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.ai.base import AIProviderError
from app.ai.images import GeneratedImage, MockImageProvider, OpenAIImageProvider, set_image_provider
from app.core.config import settings
from app.core.database import SessionLocal
from app.media.generation import run_image, run_video, video_credits
from app.models import AIUsage
from app.models.enums import AIOperation, UsageStatus
from app.storage import get_storage
from app.workers.queue import RecordingJobQueue
from tests.conftest import register_verified
from tests.media_helpers import png_bytes, upload


@pytest.fixture(autouse=True)
def _provider():  # type: ignore[no-untyped-def]
    set_image_provider(MockImageProvider())
    yield
    set_image_provider(None)


async def _ws(client: httpx.AsyncClient) -> str:
    return (await client.get("/workspaces")).json()[0]["id"]


async def _run_image(queue: RecordingJobQueue, provider=None):  # type: ignore[no-untyped-def]
    job = queue.last("generate_image")
    async with SessionLocal() as db:
        return await run_image(
            db,
            get_storage(),
            provider or MockImageProvider(),
            uuid.UUID(job["asset_id"]),
            uuid.UUID(job["usage_id"]),
        )


async def test_generate_image_reuse_and_attach(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "img@example.com")
    ws = await _ws(client)
    await client.put(
        f"/workspaces/{ws}/business/brand",
        json={"colors": ["#0E6B63"], "visual_style": "Warm, rustic wood and daylight"},
    )
    post = (
        await client.post(
            f"/workspaces/{ws}/content",
            json={"title": "New bun", "platforms": ["instagram"], "caption": "x"},
        )
    ).json()
    body = {
        "prompt": "A cardamom bun on a wooden counter",
        "aspect": "portrait",
        "content_id": post["id"],
    }
    r = await client.post(f"/workspaces/{ws}/media/generate-image", json=body)
    assert r.status_code == 202, r.text
    out = r.json()
    assert (
        out["reused"] is False
        and out["asset"]["status"] == "processing"
        and out["asset"]["source"] == "ai_generated"
    )
    assert (await client.get(f"/workspaces/{ws}/usage")).json()["images"]["used"] == 1

    await _run_image(queue)
    asset = (await client.get(f"/workspaces/{ws}/media/{out['asset']['id']}")).json()
    assert (
        asset["status"] == "ready"
        and (asset["width"], asset["height"]) == (1024, 1280)
        and asset["thumbnail_url"]
    )
    async with SessionLocal() as db:
        from app.models import MediaAsset

        row = await db.get(MediaAsset, uuid.UUID(asset["id"]))
        assert (
            "Warm, rustic wood" in row.ai_metadata["final_prompt"]
            and "#0E6B63" in row.ai_metadata["final_prompt"]
        )
        assert row.ai_metadata["provider"] == "mock"
    assert [
        m["id"]
        for m in (await client.get(f"/workspaces/{ws}/content/{post['id']}")).json()["media"]
    ] == [asset["id"]]

    again = (await client.post(f"/workspaces/{ws}/media/generate-image", json=body)).json()
    assert again["reused"] is True and again["credits"] == 0 and again["asset"]["id"] == asset["id"]
    assert (await client.get(f"/workspaces/{ws}/usage")).json()["images"]["used"] == 1


class Refusing:
    name = "refusing"
    model = "x"

    async def generate(self, prompt: str, aspect: str) -> GeneratedImage:
        raise AIProviderError("The image service refused this prompt.", retryable=False)


async def test_image_failure_refunds_and_quota(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "imgfail@example.com")
    ws = await _ws(client)
    r = (
        await client.post(
            f"/workspaces/{ws}/media/generate-image", json={"prompt": "Something odd"}
        )
    ).json()
    asset = await _run_image(queue, Refusing())
    assert asset.status.value == "failed" and "wasn't used" in asset.ai_metadata["error"]
    assert (await client.get(f"/workspaces/{ws}/usage")).json()["images"]["used"] == 0
    assert (await client.get(f"/workspaces/{ws}/media/{r['asset']['id']}")).json()["error"]

    async with SessionLocal() as db:
        for _ in range(10):
            db.add(
                AIUsage(
                    workspace_id=uuid.UUID(ws),
                    operation=AIOperation.IMAGE,
                    status=UsageStatus.COMMITTED,
                    provider="mock",
                    model="m",
                )
            )
        await db.commit()
    blocked = await client.post(
        f"/workspaces/{ws}/media/generate-image", json={"prompt": "One more"}
    )
    assert blocked.status_code == 402 and blocked.json()["error"]["details"]["bucket"] == "images"


async def test_openai_compatible_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_IMAGE_MODEL", "img-model")
    monkeypatch.setattr(settings, "AI_IMAGE_API_KEY", "sk-img")
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (1, 2, 3)).save(buf, "PNG")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["authorization"]
        if "forbidden" in seen["body"]["prompt"]:
            return httpx.Response(
                400, json={"error": {"message": "Your request was rejected by the safety system."}}
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {"b64_json": base64.b64encode(buf.getvalue()).decode(), "revised_prompt": "rp"}
                ]
            },
        )

    p = OpenAIImageProvider(
        httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://img.test/v1")
    )
    img = await p.generate("a latte", "landscape")
    assert img.mime_type == "image/png" and img.revised_prompt == "rp"
    assert (
        seen["body"] == {"model": "img-model", "prompt": "a latte", "size": "1536x1024", "n": 1}
        and seen["auth"] == "Bearer sk-img"
    )
    with pytest.raises(AIProviderError) as err:
        await p.generate("forbidden thing", "square")
    assert not err.value.retryable and "safety system" in str(err.value)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
async def test_build_video_from_own_media(
    client: httpx.AsyncClient, queue: RecordingJobQueue, tmp_path: Path
) -> None:
    await register_verified(client, queue, "video@example.com")
    ws = await _ws(client)
    photo = await upload(client, ws, png_bytes((200, 150, 90), (1200, 900)), filename="bun.png")
    clip = tmp_path / "pour.mp4"
    await asyncio.to_thread(
        subprocess.run,
        [
            shutil.which("ffmpeg") or "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=640x360:rate=24",
            "-t",
            "3",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        check=True,
    )  # noqa: S603
    video = await upload(
        client, ws, clip.read_bytes(), filename="pour.mp4", content_type="video/mp4"
    )
    scenes = [
        {"media_id": photo["id"], "duration_s": 2, "text": "Fresh today: cardamom buns"},
        {"media_id": video["id"], "duration_s": 4},  # clip is 3 s: last frame held
    ]
    r = await client.post(
        f"/workspaces/{ws}/media/build-video", json={"scenes": scenes, "title": "Morning bake"}
    )
    assert r.status_code == 202, r.text
    out = r.json()
    assert (
        out["credits"] == 1
        and out["asset"]["source"] == "assembled"
        and out["asset"]["kind"] == "video"
    )
    job = queue.last("render_video")
    async with SessionLocal() as db:
        await run_video(db, get_storage(), uuid.UUID(job["asset_id"]), uuid.UUID(job["usage_id"]))
    built = (await client.get(f"/workspaces/{ws}/media/{out['asset']['id']}")).json()
    assert built["status"] == "ready", built["error"]
    assert (
        (built["width"], built["height"]) == (1080, 1920)
        and 5.8 <= built["duration_seconds"] <= 6.3
        and built["thumbnail_url"]
    )
    assert (await client.get(f"/workspaces/{ws}/usage")).json()["video_credits"]["used"] == 1

    again = (
        await client.post(
            f"/workspaces/{ws}/media/build-video", json={"scenes": scenes, "title": "Morning bake"}
        )
    ).json()
    assert again["reused"] is True and again["credits"] == 0

    long = [{"media_id": photo["id"], "duration_s": 30}] * 3 + [
        {"media_id": photo["id"], "duration_s": 5}
    ]
    assert (await client.post(f"/workspaces/{ws}/media/build-video", json={"scenes": long})).json()[
        "error"
    ]["code"] == "video_too_long"
    bad = [{"media_id": str(uuid.uuid4()), "duration_s": 3}]
    assert (
        await client.post(f"/workspaces/{ws}/media/build-video", json={"scenes": bad})
    ).status_code == 422
    # Free has 2 video credits a month; 75 seconds needs 3 (1 credit per 30 s), and 1 is used
    costly = [{"media_id": photo["id"], "duration_s": 25}] * 3
    r = await client.post(f"/workspaces/{ws}/media/build-video", json={"scenes": costly})
    assert r.status_code == 402 and r.json()["error"]["details"]["bucket"] == "video_credits"
    assert video_credits(30) == 1 and video_credits(31) == 2 and video_credits(90) == 3
