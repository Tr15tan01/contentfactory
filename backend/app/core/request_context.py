from __future__ import annotations

from starlette.requests import Request

from app.core.config import settings


def client_ip(request: Request) -> str:
    """Resolve the client IP, trusting only the configured number of proxy hops."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and settings.TRUSTED_PROXY_COUNT > 0:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            idx = max(len(hops) - settings.TRUSTED_PROXY_COUNT, 0)
            return hops[idx]
    return request.client.host if request.client else "unknown"


def user_agent(request: Request) -> str:
    return (request.headers.get("user-agent") or "")[:400]


def client_ip_for_storage(request: Request) -> str | None:
    """Client IP validated for an INET column (test clients / unix sockets have none)."""
    import ipaddress

    ip = client_ip(request)
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None
