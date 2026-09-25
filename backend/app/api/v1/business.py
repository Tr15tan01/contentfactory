from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.auth.dependencies import DB, CurrentWorkspace
from app.models.enums import WorkspaceRole
from app.schemas.business import (
    BrandIn,
    BrandOut,
    BusinessOut,
    OnboardingIn,
    OnboardingOut,
    PreferencesIn,
    ProductIn,
    ProductOut,
    ProfileIn,
    ProfileOut,
)
from app.services import business as svc
from app.storage import Storage, get_storage

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["business"])
StorageDep = Annotated[Storage, Depends(get_storage)]
EDITORS = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.EDITOR)
MANAGERS = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)


@router.get("/business", response_model=BusinessOut)
async def get_business(ctx: CurrentWorkspace, db: DB, storage: StorageDep) -> BusinessOut:
    return await svc.get_business(db, storage, ctx.workspace)


@router.put("/business/profile", response_model=ProfileOut)
async def save_profile(body: ProfileIn, ctx: CurrentWorkspace, db: DB) -> ProfileOut:
    ctx.require_role(*MANAGERS)
    return await svc.save_profile(db, ctx.workspace, ctx.user.id, body)


@router.put("/business/brand", response_model=BrandOut)
async def save_brand(body: BrandIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep) -> BrandOut:
    ctx.require_role(*MANAGERS)
    return await svc.save_brand(db, storage, ctx.workspace, ctx.user.id, body)


@router.put("/business/preferences", response_model=PreferencesIn)
async def save_preferences(body: PreferencesIn, ctx: CurrentWorkspace, db: DB) -> PreferencesIn:
    ctx.require_role(*MANAGERS)
    return await svc.save_preferences(db, ctx.workspace, ctx.user.id, body)


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(
    body: ProductIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ProductOut:
    ctx.require_role(*EDITORS)
    return await svc.create_product(db, storage, ctx.workspace, body)


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: uuid.UUID, body: ProductIn, ctx: CurrentWorkspace, db: DB, storage: StorageDep
) -> ProductOut:
    ctx.require_role(*EDITORS)
    return await svc.update_product(db, storage, ctx.workspace, product_id, body)


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(product_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> Response:
    ctx.require_role(*EDITORS)
    await svc.delete_product(db, ctx.workspace, product_id)
    return Response(status_code=204)


@router.patch("/onboarding", response_model=OnboardingOut)
async def onboarding(body: OnboardingIn, ctx: CurrentWorkspace, db: DB) -> OnboardingOut:
    ctx.require_role(*MANAGERS)
    return await svc.set_onboarding(db, ctx.workspace, ctx.user.id, body.step, body.complete)
