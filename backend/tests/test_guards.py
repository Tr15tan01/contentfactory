"""Structural guards: every write endpoint on workspace data checks the caller's role, and
every admin endpoint requires a superuser. New routes that forget fail this test."""

from __future__ import annotations

import inspect

from fastapi.routing import APIRoute

from app.main import create_app

# Write endpoints any member may use by design (they only touch the caller's own data).
SELF_SERVICE = {"set_preferences"}


def _walk(routes: list) -> list[APIRoute]:  # type: ignore[type-arg]
    out: list[APIRoute] = []
    for r in routes:
        if isinstance(r, APIRoute):
            out.append(r)
        elif hasattr(r, "original_router"):  # included routers are nested in this FastAPI version
            out += _walk(r.original_router.routes)
        elif hasattr(r, "routes"):
            out += _walk(r.routes)
    return out


def _routes() -> list[APIRoute]:
    routes = _walk(create_app().routes)
    assert len(routes) > 80, "route discovery broke: the guards would pass vacuously"
    return routes


def test_workspace_writes_check_roles() -> None:
    missing, checked = [], 0
    for r in _routes():
        if "{workspace_id}" not in r.path or not (r.methods & {"POST", "PUT", "PATCH", "DELETE"}):
            continue
        if r.endpoint.__name__ in SELF_SERVICE:
            continue
        checked += 1
        if "require_role(" not in inspect.getsource(r.endpoint):
            missing.append(f"{sorted(r.methods)} {r.path}")
    assert checked > 30
    assert not missing, f"write endpoints without a role check: {missing}"


def test_admin_requires_superuser() -> None:
    admin = [r for r in _routes() if "/admin/" in r.path]
    assert admin
    for r in admin:
        deps = {d.call.__name__ for d in r.dependant.dependencies for d in [d, *d.dependencies]}
        assert "require_superuser" in deps, r.path
