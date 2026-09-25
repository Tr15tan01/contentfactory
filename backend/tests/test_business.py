from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Subscription, User, WorkspaceMember
from app.models.enums import Plan, WorkspaceRole
from app.workers.queue import RecordingJobQueue
from tests.conftest import register_verified
from tests.media_helpers import png_bytes, upload

PROFILE = {
    "name": "  Tbilisi   Coffee Lab ",
    "industry": "Café",
    "description": "Specialty coffee and pastries in Vake.",
    "location": "Tbilisi, Georgia",
    "website": "tbilisicoffeelab.ge",
    "audience": {
        "description": "Students and remote workers",
        "customer_types": ["Students", "students", "Remote workers"],
    },
    "unique_selling_points": ["Roasted in-house"],
    "marketing_goals": ["more_visits", "loyalty"],
    "topics_to_avoid": ["Politics"],
}


async def _ws(client: httpx.AsyncClient) -> str:
    return (await client.get("/workspaces")).json()[0]["id"]


async def test_new_workspace_business_defaults(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "biz@example.com")
    ws = await _ws(client)
    b = (await client.get(f"/workspaces/{ws}/business")).json()
    assert b["profile"] is None
    assert b["onboarding"] == {"step": 1, "completed": False}
    assert b["plan"] == "free" and b["can_auto_publish"] is False
    assert b["preferences"]["approval_required"] is True
    assert b["preferences"]["prefer_media"] == "when_relevant"


async def test_profile_save_normalises_and_renames_workspace(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "prof@example.com")
    ws = await _ws(client)
    r = await client.put(f"/workspaces/{ws}/business/profile", json=PROFILE)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["name"] == "Tbilisi Coffee Lab"
    assert p["website"] == "https://tbilisicoffeelab.ge"
    assert p["audience"]["customer_types"] == ["Students", "Remote workers"]
    assert (await client.get(f"/workspaces/{ws}")).json()["name"] == "Tbilisi Coffee Lab"

    bad = await client.put(
        f"/workspaces/{ws}/business/profile",
        json={**PROFILE, "marketing_goals": ["world_domination"]},
    )
    assert bad.status_code == 422
    bad = await client.put(
        f"/workspaces/{ws}/business/profile", json={**PROFILE, "website": "not a site"}
    )
    assert bad.status_code == 422 and "website" in bad.json()["error"]["details"]["fields"]
    assert (
        await client.put(f"/workspaces/{ws}/business/profile", json={**PROFILE, "name": "   "})
    ).status_code == 422


async def test_brand_validation_and_logo(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "brand@example.com")
    ws = await _ws(client)
    assert (
        await client.put(f"/workspaces/{ws}/business/brand", json={"colors": ["teal"]})
    ).status_code == 422
    missing = await client.put(
        f"/workspaces/{ws}/business/brand", json={"logo_asset_id": str(uuid.uuid4())}
    )
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "media_not_found"

    logo = await upload(client, ws, png_bytes((10, 10, 10), (400, 400)), filename="logo.png")
    r = await client.put(
        f"/workspaces/{ws}/business/brand",
        json={
            "voice": "Warm and direct.",
            "tone": ["friendly", "expert"],
            "colors": ["#0e6b63", "#F5D547"],
            "words_to_use": ["specialty", "fresh"],
            "words_to_avoid": ["cheap"],
            "logo_asset_id": logo["id"],
        },
    )
    assert r.status_code == 200, r.text
    brand = r.json()
    assert brand["colors"] == ["#0E6B63", "#F5D547"]
    assert brand["logo_url"] and brand["words_to_avoid"] == ["cheap"]


async def test_publishing_without_approval_needs_business_plan(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    user = await register_verified(client, queue, "pref@example.com")
    ws = await _ws(client)
    prefs = {
        "prefer_media": "always",
        "approval_required": False,
        "reminder_offsets_hours": [1, 24],
        "posts_per_week": 4,
        "preferred_platforms": ["instagram", "tiktok", "instagram"],
    }
    r = await client.put(f"/workspaces/{ws}/business/preferences", json=prefs)
    assert r.status_code == 403 and r.json()["error"]["code"] == "plan_required"

    ok = await client.put(
        f"/workspaces/{ws}/business/preferences", json={**prefs, "approval_required": True}
    )
    assert ok.status_code == 200
    assert ok.json()["reminder_offsets_hours"] == [24, 1]
    assert ok.json()["preferred_platforms"] == ["instagram", "tiktok"]

    async with SessionLocal() as db:
        sub = (
            await db.execute(
                select(Subscription).where(Subscription.user_id == uuid.UUID(user["id"]))
            )
        ).scalar_one()
        sub.manual_plan_override = Plan.BUSINESS
        await db.commit()
    assert (
        await client.put(f"/workspaces/{ws}/business/preferences", json=prefs)
    ).status_code == 200
    assert (await client.get(f"/workspaces/{ws}/business")).json()["can_auto_publish"] is True


async def test_products_crud_with_media(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    make_client,  # type: ignore[no-untyped-def]
) -> None:
    await register_verified(client, queue, "prod@example.com")
    ws = await _ws(client)
    photo = await upload(client, ws, png_bytes((90, 50, 20)), filename="cappuccino.png")
    r = await client.post(
        f"/workspaces/{ws}/products",
        json={
            "name": "Cappuccino",
            "price": "7.50",
            "currency": "GEL",
            "benefits": ["Oat milk available"],
            "media_ids": [photo["id"]],
        },
    )
    assert r.status_code == 201, r.text
    product = r.json()
    assert product["price"] == "7.50" and len(product["thumbnails"]) == 1

    other = await make_client()
    await register_verified(other, queue, "prod-other@example.com")
    other_ws = await _ws(other)
    foreign = await other.post(
        f"/workspaces/{other_ws}/products", json={"name": "Stolen", "media_ids": [photo["id"]]}
    )
    assert foreign.status_code == 422
    assert (
        await other.delete(f"/workspaces/{other_ws}/products/{product['id']}")
    ).status_code == 404

    upd = await client.put(
        f"/workspaces/{ws}/products/{product['id']}",
        json={"name": "Cappuccino", "price": "8.00", "media_ids": []},
    )
    assert upd.json()["price"] == "8.00" and upd.json()["media_ids"] == []
    await client.post(f"/workspaces/{ws}/products", json={"name": "Cold brew"})
    names = [p["name"] for p in (await client.get(f"/workspaces/{ws}/business")).json()["products"]]
    assert names == ["Cappuccino", "Cold brew"]
    assert (await client.delete(f"/workspaces/{ws}/products/{product['id']}")).status_code == 204
    assert len((await client.get(f"/workspaces/{ws}/business")).json()["products"]) == 1


async def test_onboarding_completion_clears_dashboard_prompt(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "onb@example.com")
    ws = await _ws(client)
    kinds = lambda d: [a["kind"] for a in d["attention"]]  # noqa: E731
    assert "finish_onboarding" in kinds((await client.get(f"/workspaces/{ws}/dashboard")).json())
    assert (await client.patch(f"/workspaces/{ws}/onboarding", json={"step": 3})).json() == {
        "step": 3,
        "completed": False,
    }
    assert (await client.patch(f"/workspaces/{ws}/onboarding", json={"step": 2})).json()[
        "step"
    ] == 3  # never goes back
    done = await client.patch(f"/workspaces/{ws}/onboarding", json={"step": 7, "complete": True})
    assert done.json() == {"step": 7, "completed": True}
    assert (await client.get(f"/workspaces/{ws}")).json()["onboarding_completed"] is True
    assert "finish_onboarding" not in kinds(
        (await client.get(f"/workspaces/{ws}/dashboard")).json()
    )


async def test_editor_cannot_change_business_profile(
    client: httpx.AsyncClient,
    queue: RecordingJobQueue,
    make_client,  # type: ignore[no-untyped-def]
) -> None:
    await register_verified(client, queue, "own-b@example.com")
    ws = await _ws(client)
    editor = await make_client()
    await register_verified(editor, queue, "edit-b@example.com")
    async with SessionLocal() as db:
        u = (await db.execute(select(User).where(User.email == "edit-b@example.com"))).scalar_one()
        db.add(WorkspaceMember(workspace_id=uuid.UUID(ws), user_id=u.id, role=WorkspaceRole.EDITOR))
        await db.commit()
    assert (await editor.put(f"/workspaces/{ws}/business/profile", json=PROFILE)).status_code == 403
    assert (
        await editor.post(f"/workspaces/{ws}/products", json={"name": "Latte"})
    ).status_code == 201
