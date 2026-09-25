"""Painted stand-in photos for the demo workspace (no stock imagery, no network)."""

from __future__ import annotations

import io
import random
import uuid

from PIL import Image, ImageDraw, ImageFilter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.processing import process_asset
from app.models import MediaAsset, MediaFolder, Product, ProductMedia, Workspace
from app.models.enums import MediaKind, MediaSource, MediaStatus
from app.storage import get_storage

# name, tags, description, background gradient, shapes, product
SCENES = [
    (
        "Morning espresso",
        ["espresso", "bar"],
        "A double espresso on the bar at opening time.",
        ((59, 36, 24), (138, 90, 60)),
        [
            ("circle", (0.42, 0.45, 0.2), (198, 138, 85)),
            ("circle", (0.42, 0.45, 0.13), (90, 50, 29)),
        ],
        "Espresso",
    ),
    (
        "Flat white, rosetta",
        ["latte art", "milk"],
        "Flat white with a rosetta, from above.",
        ((217, 194, 165), (156, 118, 82)),
        [
            ("circle", (0.5, 0.5, 0.3), (122, 79, 49)),
            ("circle", (0.5, 0.5, 0.24), (199, 155, 109)),
            ("circle", (0.5, 0.48, 0.12), (244, 230, 212)),
        ],
        "Cappuccino",
    ),
    (
        "Cold brew bottles",
        ["cold brew", "summer"],
        "Bottled cold brew lined up on the counter.",
        ((185, 141, 99), (107, 74, 51)),
        [
            ("rect", (0.3, 0.25, 0.14, 0.6), (36, 20, 12)),
            ("rect", (0.5, 0.25, 0.14, 0.6), (36, 20, 12)),
            ("rect", (0.7, 0.25, 0.14, 0.6), (36, 20, 12)),
        ],
        "Cold Brew",
    ),
    (
        "Cardamom buns",
        ["pastries", "baking"],
        "Fresh cardamom buns out of the oven.",
        ((239, 226, 207), (201, 165, 124)),
        [
            ("circle", (0.35, 0.55, 0.18), (184, 115, 47)),
            ("circle", (0.65, 0.45, 0.16), (233, 184, 103)),
        ],
        "Pastries",
    ),
    (
        "Roaster on Tuesday",
        ["roasting", "behind the scenes"],
        "Tuesday roast, beans cooling in the tray.",
        ((58, 42, 32), (31, 21, 16)),
        [("circle", (0.5, 0.6, 0.34), (92, 60, 38)), ("circle", (0.5, 0.6, 0.28), (60, 38, 24))],
        None,
    ),
    (
        "Window seats",
        ["space", "vake"],
        "Window seats in the afternoon light.",
        ((226, 214, 190), (140, 120, 96)),
        [
            ("rect", (0.1, 0.1, 0.35, 0.55), (250, 240, 220)),
            ("rect", (0.55, 0.1, 0.35, 0.55), (250, 240, 220)),
        ],
        None,
    ),
]


def _paint(bg: tuple[tuple[int, int, int], tuple[int, int, int]], shapes: list, seed: int) -> bytes:
    w, h = 1600, 1200
    rng = random.Random(seed)
    im = Image.new("RGB", (w, h))
    top, bottom = bg
    draw = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        draw.line(
            [(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        )
    for kind, geo, color in shapes:
        if kind == "circle":
            cx, cy, r = geo
            draw.ellipse(
                [
                    (cx - r) * w * 0.75 + w * 0.125,
                    cy * h - r * h,
                    (cx + r) * w * 0.75 + w * 0.125,
                    cy * h + r * h,
                ],
                fill=color,
            )
        else:
            x, y, rw, rh = geo
            draw.rounded_rectangle(
                [x * w, y * h, (x + rw) * w, (y + rh) * h], radius=24, fill=color
            )
    im = im.filter(ImageFilter.GaussianBlur(2))
    noise = Image.effect_noise((w, h), 18).convert("RGB")
    im = Image.blend(im, noise, 0.04 + rng.random() * 0.02)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=86)
    return buf.getvalue()


async def seed_media(db: AsyncSession, ws: Workspace, owner_id: uuid.UUID) -> int:
    storage = get_storage()
    folder = MediaFolder(workspace_id=ws.id, name="Menu")
    db.add(folder)
    await db.flush()
    products = {
        p.name: p
        for p in (await db.execute(select(Product).where(Product.workspace_id == ws.id))).scalars()
    }
    for i, (name, tags, desc, bg, shapes, product) in enumerate(SCENES):
        data = _paint(bg, shapes, i)
        asset_id = uuid.uuid4()
        slug = name.lower().replace(" ", "-").replace(",", "")
        key = f"workspaces/{ws.id}/media/{asset_id}/{slug}.jpg"
        await storage.put(key, data, "image/jpeg")
        db.add(
            MediaAsset(
                id=asset_id,
                workspace_id=ws.id,
                folder_id=folder.id if product else None,
                uploaded_by_id=owner_id,
                kind=MediaKind.IMAGE,
                source=MediaSource.UPLOAD,
                status=MediaStatus.PROCESSING,
                storage_bucket=storage.bucket,
                storage_key=key,
                mime_type="image/jpeg",
                size_bytes=len(data),
                original_filename=key.rsplit("/", 1)[1],
                display_name=name,
                alt_text=desc,
                tags=tags,
                ai_metadata={"demo": True},
                is_favorite=i == 2,
            )
        )
        await db.commit()
        await process_asset(db, storage, asset_id)
        if product and product in products:
            db.add(
                ProductMedia(product_id=products[product].id, media_asset_id=asset_id, position=0)
            )
            await db.commit()
    return len(SCENES)


async def delete_media_files(db: AsyncSession, workspace_ids: list[uuid.UUID]) -> None:
    storage = get_storage()
    rows = await db.execute(
        select(MediaAsset.storage_key, MediaAsset.thumbnail_key).where(
            MediaAsset.workspace_id.in_(workspace_ids)
        )
    )
    for key, thumb in rows.all():
        for k in (key, thumb):
            if k:
                await storage.delete(k)
