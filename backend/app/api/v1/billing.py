from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import DB, CurrentUser
from app.billing import paddle
from app.billing import service as svc
from app.core.errors import AppError
from app.schemas.billing import BillingOut, CheckoutOut, PendingOut, PlanIn, PortalOut

router = APIRouter(prefix="/billing", tags=["billing"])
log = logging.getLogger("contentfactory.billing")
PaddleDep = Annotated[paddle.PaddleClient, Depends(paddle.get_paddle)]


@router.get("", response_model=BillingOut)
async def get_billing(user: CurrentUser, db: DB) -> BillingOut:
    out = BillingOut.model_validate(await svc.overview(db, user))
    await db.commit()
    return out


@router.post("/checkout", response_model=CheckoutOut)
async def checkout(body: PlanIn, user: CurrentUser, db: DB) -> CheckoutOut:
    return CheckoutOut.model_validate(await svc.checkout(db, user, body.plan))


@router.post("/change-plan", response_model=PendingOut, status_code=202)
async def change_plan(body: PlanIn, user: CurrentUser, db: DB, client: PaddleDep) -> PendingOut:
    return PendingOut.model_validate(await svc.change_plan(db, client, user, body.plan))


@router.post("/cancel", response_model=PendingOut, status_code=202)
async def cancel(user: CurrentUser, db: DB, client: PaddleDep) -> PendingOut:
    return PendingOut.model_validate(await svc.cancel(db, client, user))


@router.post("/resume", response_model=PendingOut, status_code=202)
async def resume(user: CurrentUser, db: DB, client: PaddleDep) -> PendingOut:
    return PendingOut.model_validate(await svc.resume(db, client, user))


@router.post("/portal", response_model=PortalOut)
async def portal(user: CurrentUser, db: DB, client: PaddleDep) -> PortalOut:
    return PortalOut(url=await svc.portal(db, client, user))


@router.post("/webhooks/paddle", include_in_schema=False)
async def paddle_webhook(request: Request, db: DB) -> JSONResponse:
    """Signature-verified, idempotent, order-safe. CSRF-exempt (authenticated by signature)."""
    raw = await request.body()
    if not paddle.verify_signature(raw, request.headers.get("paddle-signature")):
        raise AppError(401, "invalid_signature", "Invalid webhook signature.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError(400, "invalid_json", "Body is not JSON.") from exc
    event = await svc.record_event(db, payload)
    if event is None:
        await db.commit()
        return JSONResponse({"status": "duplicate"})
    # A processing crash rolls everything back and returns 500, so Paddle retries later.
    result = await svc.process_event(db, event)
    await db.commit()
    log.info("paddle %s %s -> %s", event.event_type, event.paddle_event_id, result)
    return JSONResponse({"status": result})
