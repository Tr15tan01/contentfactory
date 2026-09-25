from __future__ import annotations

import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from app.auth.dependencies import DB, CurrentWorkspace, Queue
from app.core.config import settings
from app.models.enums import WorkspaceRole
from app.schemas.content import PublicationOut
from app.schemas.social import ConnectOut, SocialOut
from app.social import publisher
from app.social import service as svc
from app.social.base import SocialError

router = APIRouter(tags=["social"])
MANAGERS = (WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
EDITORS = (*MANAGERS, WorkspaceRole.EDITOR)
COOKIE_PATH = f"{settings.API_PREFIX}/social/callback"


@router.get("/workspaces/{workspace_id}/social", response_model=SocialOut)
async def overview(ctx: CurrentWorkspace, db: DB) -> SocialOut:
    accounts, limit = await svc.list_accounts(db, ctx.workspace)
    return SocialOut.model_validate(
        {
            "providers": svc.providers(await svc.connected_counts(db, ctx.workspace)),
            "accounts": accounts,
            "limit": limit,
            # Platforms fetch media from our URLs; local disk storage isn't reachable by them.
            "publishing_needs_public_media": settings.STORAGE_PROVIDER == "local",
        }
    )


@router.post("/workspaces/{workspace_id}/social/{provider}/connect", response_model=ConnectOut)
async def connect(provider: str, ctx: CurrentWorkspace) -> JSONResponse:
    ctx.require_role(*MANAGERS)
    url, cookie = svc.start_connect(ctx.workspace, ctx.user, provider)
    response = JSONResponse({"authorize_url": url})
    response.set_cookie(
        svc.STATE_COOKIE,
        cookie,
        max_age=svc.STATE_TTL,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path=COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
    )
    return response


@router.get("/social/callback/{provider}", include_in_schema=False)
async def callback(provider: str, request: Request, db: DB) -> RedirectResponse:
    """The provider redirects the browser here. Always ends on the Social accounts page."""
    target = f"{settings.APP_URL.rstrip('/')}/settings/social"
    params = request.query_params
    try:
        state = svc.read_state(request.cookies.get(svc.STATE_COOKIE), params.get("state"), provider)
        if params.get("error"):
            raise SocialError("The connection was cancelled.", code="cancelled")
        result = await svc.finish_connect(db, provider, params.get("code") or "", state)
        query = {
            "connected": result["connected"],
            "reconnected": result["reconnected"],
            "skipped": result["skipped"],
            "provider": provider,
        }
    except SocialError as exc:
        await db.rollback()
        query = {"error": exc.code, "message": str(exc)[:200], "provider": provider}
    response = RedirectResponse(f"{target}?{urlencode(query)}", status_code=303)
    response.delete_cookie(svc.STATE_COOKIE, path=COOKIE_PATH, domain=settings.COOKIE_DOMAIN)
    return response


@router.delete("/workspaces/{workspace_id}/social/accounts/{account_id}", status_code=204)
async def disconnect(account_id: uuid.UUID, ctx: CurrentWorkspace, db: DB) -> Response:
    ctx.require_role(*MANAGERS)
    await svc.disconnect(db, ctx.workspace, ctx.user, account_id)
    return Response(status_code=204)


@router.post(
    "/workspaces/{workspace_id}/publications/{publication_id}/retry", response_model=PublicationOut
)
async def retry(
    publication_id: uuid.UUID, ctx: CurrentWorkspace, db: DB, queue: Queue
) -> PublicationOut:
    ctx.require_role(*EDITORS)
    pub = await publisher.retry(db, queue, ctx.workspace.id, publication_id)
    return PublicationOut.model_validate(pub, from_attributes=True)
