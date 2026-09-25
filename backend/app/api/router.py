from fastapi import APIRouter

from app.api.v1 import (
    activity,
    admin,
    billing,
    business,
    content,
    health,
    intelligence,
    media,
    public,
    social,
    storage,
    workspaces,
)
from app.auth.router import router as auth_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_router)
api_router.include_router(workspaces.router)
api_router.include_router(public.router)
api_router.include_router(media.router)
api_router.include_router(content.router)
api_router.include_router(billing.router)
api_router.include_router(social.router)
api_router.include_router(intelligence.router)
api_router.include_router(activity.router)
api_router.include_router(admin.router)
api_router.include_router(business.router)
api_router.include_router(storage.router)
