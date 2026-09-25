from __future__ import annotations

import io
import uuid

import httpx
from PIL import Image

from app.core.database import SessionLocal
from app.media.processing import process_asset
from app.storage import get_storage


def png_bytes(
    color: tuple[int, int, int] = (14, 107, 99), size: tuple[int, int] = (1200, 800)
) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


async def upload(
    client: httpx.AsyncClient,
    ws: str,
    data: bytes,
    *,
    filename: str = "latte art.png",
    content_type: str = "image/png",
    process: bool = True,
) -> dict:
    r = await client.post(
        f"/workspaces/{ws}/media/uploads",
        json={"filename": filename, "content_type": content_type, "size_bytes": len(data)},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    target = body["upload"]
    put = await client.request(
        target["method"],
        f"http://testserver{target['url']}",
        content=data,
        headers=target["headers"],
    )
    assert put.status_code == 204, put.text
    done = await client.post(f"/workspaces/{ws}/media/{body['asset']['id']}/complete")
    assert done.status_code == 200, done.text
    if process:
        async with SessionLocal() as db:
            await process_asset(db, get_storage(), uuid.UUID(body["asset"]["id"]))
        return (await client.get(f"/workspaces/{ws}/media/{body['asset']['id']}")).json()
    return done.json()
