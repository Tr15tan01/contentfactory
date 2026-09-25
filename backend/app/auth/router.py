from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, update

from app.auth import google
from app.auth.dependencies import DB, CurrentAuth, Queue
from app.auth.serializers import session_out, user_out
from app.auth.service import AuthService
from app.core.config import settings
from app.core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies, set_csrf_cookie
from app.core.errors import AppError, envelope, not_found
from app.core.rate_limit import rate_limit
from app.core.security import decode_access_token, utcnow
from app.models import Session
from app.schemas.auth import (
    AuthConfigOut,
    ChangePasswordIn,
    CsrfOut,
    DeleteAccountIn,
    EmailIn,
    LoginIn,
    RegisterIn,
    RegisterOut,
    ResetPasswordIn,
    SessionOut,
    TokenIn,
    UpdateProfileIn,
    UserOut,
)
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def get_service(request: Request, db: DB, queue: Queue) -> AuthService:
    return AuthService(db, request, queue)


Service = Annotated[AuthService, Depends(get_service)]


@router.get("/config", response_model=AuthConfigOut)
async def auth_config() -> AuthConfigOut:
    return AuthConfigOut(
        google_enabled=settings.AUTH_GOOGLE_ENABLED,
        email_verification_required=settings.AUTH_REQUIRE_EMAIL_VERIFICATION,
        password_min_length=settings.PASSWORD_MIN_LENGTH,
    )


@router.get("/csrf", response_model=CsrfOut)
async def csrf(request: Request, response: Response) -> CsrfOut:
    existing = request.cookies.get("cf_csrf")
    return CsrfOut(csrf_token=set_csrf_cookie(response, existing))


@router.post(
    "/register",
    response_model=RegisterOut,
    status_code=201,
    dependencies=[Depends(rate_limit("register", 10, 3600))],
)
async def register(body: RegisterIn, response: Response, service: Service) -> RegisterOut:
    user, issued = await service.register(body.email, body.password, body.full_name)
    if issued and user:
        set_auth_cookies(response, issued.access_token, issued.refresh_token)
        return RegisterOut(verification_required=False, user=user_out(user))
    return RegisterOut(verification_required=True)


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, response: Response, service: Service) -> UserOut:
    user, issued = await service.login(body.email, body.password)
    set_auth_cookies(response, issued.access_token, issued.refresh_token)
    return user_out(user)


@router.post("/refresh", status_code=204, dependencies=[Depends(rate_limit("refresh", 60, 60))])
async def refresh(request: Request, service: Service) -> Response:
    try:
        issued = await service.refresh(request.cookies.get(REFRESH_COOKIE))
    except AppError as exc:
        if exc.code != "session_expired":
            raise
        expired = JSONResponse(envelope(exc.code, exc.message), status_code=401)
        clear_auth_cookies(expired)
        return expired
    response = Response(status_code=204)
    set_auth_cookies(response, issued.access_token, issued.refresh_token)
    return response


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, service: Service) -> Response:
    payload = decode_access_token(request.cookies.get("cf_access", ""))
    sid = uuid.UUID(payload["sid"]) if payload else None
    await service.logout(sid, request.cookies.get(REFRESH_COOKIE))
    clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
async def me(ctx: CurrentAuth) -> UserOut:
    return user_out(ctx.user)


@router.patch("/me", response_model=UserOut)
async def update_me(body: UpdateProfileIn, ctx: CurrentAuth, db: DB) -> UserOut:
    if body.full_name is not None:
        ctx.user.full_name = body.full_name.strip() or None
    if body.timezone is not None:
        ctx.user.timezone = body.timezone
    await db.commit()
    return user_out(ctx.user)


@router.post("/verify-email", response_model=UserOut)
async def verify_email(body: TokenIn, response: Response, service: Service) -> UserOut:
    user, issued = await service.verify_email(body.token)
    set_auth_cookies(response, issued.access_token, issued.refresh_token)
    return user_out(user)


@router.post(
    "/verify-email/resend",
    status_code=202,
    dependencies=[Depends(rate_limit("verify-resend", 10, 3600))],
)
async def resend_verification(body: EmailIn, service: Service) -> dict[str, str]:
    await service.resend_verification(body.email)
    return {"status": "If that account needs confirming, we've sent a new link."}


@router.post(
    "/password/forgot", status_code=202, dependencies=[Depends(rate_limit("forgot-ip", 10, 3600))]
)
async def forgot_password(body: EmailIn, service: Service) -> dict[str, str]:
    await service.forgot_password(body.email)
    return {"status": "If an account exists for that email, we've sent a reset link."}


@router.post(
    "/password/reset", status_code=204, dependencies=[Depends(rate_limit("reset", 20, 3600))]
)
async def reset_password(body: ResetPasswordIn, response: Response, service: Service) -> Response:
    await service.reset_password(body.token, body.password)
    clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.post("/password/change", status_code=204)
async def change_password(
    body: ChangePasswordIn, ctx: CurrentAuth, service: Service, response: Response
) -> Response:
    await service.change_password(
        ctx.user, ctx.session.id, body.current_password, body.new_password
    )
    response.status_code = 204
    return response


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(ctx: CurrentAuth, db: DB) -> list[SessionOut]:
    rows = (
        (
            await db.execute(
                select(Session)
                .where(
                    Session.user_id == ctx.user.id,
                    Session.revoked_at.is_(None),
                    Session.expires_at > utcnow(),
                )
                .order_by(Session.last_used_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [session_out(s, ctx.session.id) for s in rows]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: uuid.UUID, ctx: CurrentAuth, db: DB, response: Response
) -> Response:
    result = await db.execute(
        update(Session)
        .where(
            Session.id == session_id, Session.user_id == ctx.user.id, Session.revoked_at.is_(None)
        )
        .values(revoked_at=utcnow(), revoked_reason="user_revoked")
    )
    if not result.rowcount:
        raise not_found("Session")
    audit.record(
        db,
        "auth.session_revoked",
        actor_user_id=ctx.user.id,
        entity_type="session",
        entity_id=session_id,
    )
    await db.commit()
    if session_id == ctx.session.id:
        clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.post("/sessions/revoke-others", status_code=204)
async def revoke_other_sessions(
    ctx: CurrentAuth, service: Service, db: DB, response: Response
) -> Response:
    await service.revoke_all_sessions(ctx.user.id, "user_revoked", except_id=ctx.session.id)
    audit.record(db, "auth.sessions_revoked", actor_user_id=ctx.user.id)
    await db.commit()
    response.status_code = 204
    return response


@router.post("/account/delete", status_code=204)
async def delete_account(
    body: DeleteAccountIn, ctx: CurrentAuth, service: Service, response: Response
) -> Response:
    await service.delete_account(ctx.user, body.password, body.confirm_email)
    clear_auth_cookies(response)
    response.status_code = 204
    return response


# ---------------------------------------------------------------------------- Google OAuth
def _google_enabled() -> None:
    if not settings.AUTH_GOOGLE_ENABLED:
        raise not_found()


@router.get("/google/start", dependencies=[Depends(_google_enabled)])
async def google_start(
    next: Annotated[str | None, Query(max_length=300)] = None,
) -> RedirectResponse:
    url, cookie = google.start(next)
    resp = RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        google.STATE_COOKIE,
        cookie,
        max_age=600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path=f"{settings.API_PREFIX}/auth/google",
    )
    return resp


@router.get("/google/callback", dependencies=[Depends(_google_enabled)])
async def google_callback(
    request: Request,
    service: Service,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    login_url = f"{settings.APP_URL}/login"
    try:
        if error or not code:
            raise AppError(400, "oauth_cancelled", "Google sign-in was cancelled.")
        verifier, next_path = google.read_state(request.cookies.get(google.STATE_COOKIE), state)
        profile = await google.fetch_profile(code, verifier)
        _, issued, created = await service.login_with_google(profile)
    except AppError as exc:
        resp = RedirectResponse(f"{login_url}?error={exc.code}", status_code=302)
    else:
        target = "/onboarding" if created else next_path
        resp = RedirectResponse(f"{settings.APP_URL}{target}", status_code=302)
        set_auth_cookies(resp, issued.access_token, issued.refresh_token)
    resp.delete_cookie(google.STATE_COOKIE, path=f"{settings.API_PREFIX}/auth/google")
    return resp
