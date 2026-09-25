"""Business profile, brand, products, publishing preferences and onboarding progress."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.entitlements import plan_required, workspace_plan
from app.core.errors import AppError, not_found
from app.core.security import utcnow
from app.models import Brand, BusinessProfile, MediaAsset, Product, ProductMedia, Workspace
from app.models.enums import MediaKind, MediaStatus
from app.schemas.business import (
    BrandIn,
    BrandOut,
    BusinessOut,
    OnboardingOut,
    PreferencesIn,
    ProductIn,
    ProductOut,
    ProfileIn,
    ProfileOut,
)
from app.services import audit
from app.storage import Storage

MAX_PRODUCTS = 200


async def _profile(db: AsyncSession, ws: Workspace) -> BusinessProfile | None:
    return (
        await db.execute(select(BusinessProfile).where(BusinessProfile.workspace_id == ws.id))
    ).scalar_one_or_none()


async def _ensure_profile(db: AsyncSession, ws: Workspace) -> BusinessProfile:
    profile = await _profile(db, ws)
    if profile is None:
        profile = BusinessProfile(workspace_id=ws.id, name=ws.name)
        db.add(profile)
        await db.flush()
    return profile


async def _brand(db: AsyncSession, ws: Workspace) -> Brand | None:
    return (await db.execute(select(Brand).where(Brand.workspace_id == ws.id))).scalar_one_or_none()


async def _ready_media(
    db: AsyncSession, ws: Workspace, ids: list[uuid.UUID], kind: MediaKind | None = None
) -> list[MediaAsset]:
    if not ids:
        return []
    rows = (
        (
            await db.execute(
                select(MediaAsset).where(
                    MediaAsset.id.in_(ids),
                    MediaAsset.workspace_id == ws.id,
                    MediaAsset.deleted_at.is_(None),
                    MediaAsset.status == MediaStatus.READY,
                )
            )
        )
        .scalars()
        .all()
    )
    found = {a.id: a for a in rows if kind is None or a.kind is kind}
    if len(found) != len(set(ids)):
        raise AppError(422, "media_not_found", "One of the selected files isn't in your library.")
    return [found[i] for i in ids]


def _profile_out(p: BusinessProfile) -> ProfileOut:
    return ProfileOut.model_validate(
        {
            "name": p.name,
            "industry": p.industry,
            "description": p.description,
            "location": p.location,
            "website": p.website,
            "preferred_language": p.preferred_language,
            "audience": p.audience or {},
            "unique_selling_points": p.unique_selling_points or [],
            "competitors": p.competitors or [],
            "marketing_goals": p.marketing_goals or [],
            "topics_to_avoid": p.topics_to_avoid or [],
        }
    )


async def _brand_out(
    db: AsyncSession, storage: Storage, ws: Workspace, b: Brand | None
) -> BrandOut:
    if b is None:
        return BrandOut()
    logo_url = None
    if b.logo_asset_id:
        logo = await db.get(MediaAsset, b.logo_asset_id)
        if logo and logo.deleted_at is None and logo.status is MediaStatus.READY:
            logo_url = storage.download_url(logo.thumbnail_key or logo.storage_key)
    g = b.guidelines or {}
    return BrandOut(
        voice=b.voice,
        tone=b.tone or [],
        colors=b.colors or [],
        visual_style=b.visual_style,
        words_to_use=g.get("words_to_use", []),
        words_to_avoid=g.get("words_to_avoid", []),
        logo_asset_id=b.logo_asset_id,
        logo_url=logo_url,
    )


def _preferences(ws: Workspace, p: BusinessProfile | None) -> PreferencesIn:
    s: dict[str, Any] = ws.settings or {}
    return PreferencesIn(
        prefer_media=s.get("prefer_media", "when_relevant"),
        approval_required=s.get("approval_required", True),
        reminder_offsets_hours=s.get("reminder_offsets_hours", [24]),
        posts_per_week=s.get("posts_per_week", 3),
        preferred_platforms=(p.preferred_platforms if p else []) or [],
    )


async def _products(db: AsyncSession, storage: Storage, ws: Workspace) -> list[ProductOut]:
    products = (
        (
            await db.execute(
                select(Product)
                .where(Product.workspace_id == ws.id, Product.deleted_at.is_(None))
                .order_by(Product.position, Product.created_at)
            )
        )
        .scalars()
        .all()
    )
    links = (
        await db.execute(
            select(ProductMedia.product_id, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ProductMedia.media_asset_id)
            .where(
                ProductMedia.product_id.in_([p.id for p in products] or [uuid.uuid4()]),
                MediaAsset.deleted_at.is_(None),
            )
            .order_by(ProductMedia.position)
        )
    ).all()
    media: dict[uuid.UUID, list[MediaAsset]] = {}
    for pid, asset in links:
        media.setdefault(pid, []).append(asset)
    return [
        ProductOut(
            id=p.id,
            position=p.position,
            name=p.name,
            description=p.description,
            price=p.price,
            currency=p.currency,
            benefits=p.benefits or [],
            target_customer=p.target_customer,
            url=p.url,
            media_ids=[a.id for a in media.get(p.id, [])],
            thumbnails=[
                storage.download_url(a.thumbnail_key or a.storage_key)
                for a in media.get(p.id, [])
                if a.status is MediaStatus.READY
            ],
        )
        for p in products
    ]


async def get_business(db: AsyncSession, storage: Storage, ws: Workspace) -> BusinessOut:
    profile = await _profile(db, ws)
    plan = await workspace_plan(db, ws)
    return BusinessOut(
        profile=_profile_out(profile) if profile else None,
        brand=await _brand_out(db, storage, ws, await _brand(db, ws)),
        preferences=_preferences(ws, profile),
        products=await _products(db, storage, ws),
        onboarding=OnboardingOut(
            step=profile.onboarding_step if profile else 1,
            completed=bool(profile and profile.onboarding_completed_at),
        ),
        plan=plan.name.lower(),
        can_auto_publish=plan.auto_publish,
    )


async def save_profile(
    db: AsyncSession, ws: Workspace, user_id: uuid.UUID, body: ProfileIn
) -> ProfileOut:
    profile = await _ensure_profile(db, ws)
    data = body.model_dump(mode="json")
    for key, value in data.items():
        setattr(profile, key, value)
    if ws.name != body.name:  # the workspace is named after the business
        ws.name = body.name
    audit.record(db, "business.profile_saved", actor_user_id=user_id, workspace_id=ws.id)
    await db.commit()
    return _profile_out(profile)


async def save_brand(
    db: AsyncSession, storage: Storage, ws: Workspace, user_id: uuid.UUID, body: BrandIn
) -> BrandOut:
    if body.logo_asset_id:
        await _ready_media(db, ws, [body.logo_asset_id], MediaKind.IMAGE)
    brand = await _brand(db, ws)
    if brand is None:
        brand = Brand(workspace_id=ws.id)
        db.add(brand)
    brand.voice = body.voice.strip() if body.voice else None
    brand.tone = body.tone
    brand.colors = body.colors
    brand.visual_style = body.visual_style.strip() if body.visual_style else None
    brand.logo_asset_id = body.logo_asset_id
    brand.guidelines = {
        **(brand.guidelines or {}),
        "words_to_use": body.words_to_use,
        "words_to_avoid": body.words_to_avoid,
    }
    audit.record(db, "business.brand_saved", actor_user_id=user_id, workspace_id=ws.id)
    await db.commit()
    return await _brand_out(db, storage, ws, brand)


async def save_preferences(
    db: AsyncSession, ws: Workspace, user_id: uuid.UUID, body: PreferencesIn
) -> PreferencesIn:
    if not body.approval_required:
        plan = await workspace_plan(db, ws)
        if not plan.auto_publish:
            raise plan_required("Publishing without approval")
    ws.settings = {
        **(ws.settings or {}),
        "prefer_media": body.prefer_media,
        "approval_required": body.approval_required,
        "reminder_offsets_hours": sorted(set(body.reminder_offsets_hours), reverse=True),
        "posts_per_week": body.posts_per_week,
    }
    profile = await _ensure_profile(db, ws)
    profile.preferred_platforms = [p.value for p in dict.fromkeys(body.preferred_platforms)]
    profile.posting_frequency = f"{body.posts_per_week}/week"
    audit.record(
        db,
        "business.preferences_saved",
        actor_user_id=user_id,
        workspace_id=ws.id,
        data={"approval_required": body.approval_required},
    )
    await db.commit()
    return _preferences(ws, profile)


async def _set_product_media(
    db: AsyncSession, ws: Workspace, product: Product, ids: list[uuid.UUID]
) -> None:
    ids = list(dict.fromkeys(ids))
    await _ready_media(db, ws, ids)
    await db.execute(delete(ProductMedia).where(ProductMedia.product_id == product.id))
    for pos, mid in enumerate(ids):
        db.add(ProductMedia(product_id=product.id, media_asset_id=mid, position=pos))


async def _get_product(db: AsyncSession, ws: Workspace, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None or product.workspace_id != ws.id or product.deleted_at is not None:
        raise not_found("Product")
    return product


async def create_product(
    db: AsyncSession, storage: Storage, ws: Workspace, body: ProductIn
) -> ProductOut:
    count, max_pos = (
        await db.execute(
            select(func.count(), func.coalesce(func.max(Product.position), -1)).where(
                Product.workspace_id == ws.id, Product.deleted_at.is_(None)
            )
        )
    ).one()
    if count >= MAX_PRODUCTS:
        raise AppError(409, "too_many_products", f"You can add up to {MAX_PRODUCTS} products.")
    data = body.model_dump(exclude={"media_ids"})
    product = Product(workspace_id=ws.id, position=max_pos + 1, **data)
    db.add(product)
    await db.flush()
    await _set_product_media(db, ws, product, body.media_ids)
    await db.commit()
    return next(p for p in await _products(db, storage, ws) if p.id == product.id)


async def update_product(
    db: AsyncSession, storage: Storage, ws: Workspace, product_id: uuid.UUID, body: ProductIn
) -> ProductOut:
    product = await _get_product(db, ws, product_id)
    for key, value in body.model_dump(exclude={"media_ids"}).items():
        setattr(product, key, value)
    await _set_product_media(db, ws, product, body.media_ids)
    await db.commit()
    return next(p for p in await _products(db, storage, ws) if p.id == product.id)


async def delete_product(db: AsyncSession, ws: Workspace, product_id: uuid.UUID) -> None:
    product = await _get_product(db, ws, product_id)
    product.deleted_at = utcnow()
    await db.commit()


async def set_onboarding(
    db: AsyncSession, ws: Workspace, user_id: uuid.UUID, step: int, complete: bool
) -> OnboardingOut:
    profile = await _ensure_profile(db, ws)
    profile.onboarding_step = max(profile.onboarding_step, step) if not complete else step
    if complete and profile.onboarding_completed_at is None:
        profile.onboarding_completed_at = utcnow()
        audit.record(db, "onboarding.completed", actor_user_id=user_id, workspace_id=ws.id)
    await db.commit()
    return OnboardingOut(
        step=profile.onboarding_step, completed=profile.onboarding_completed_at is not None
    )
