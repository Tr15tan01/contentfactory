from __future__ import annotations

import httpx

from app.workers.queue import RecordingJobQueue
from tests.conftest import register_verified


async def test_profile_timezone_must_be_iana(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "tz@example.com")
    r = await client.patch("/auth/me", json={"timezone": "Mars/Olympus_Mons"})
    assert r.status_code == 422
    assert "timezone" in r.json()["error"]["details"]["fields"]

    r = await client.patch("/auth/me", json={"timezone": "Asia/Tbilisi", "full_name": "  Nino  "})
    assert r.status_code == 200
    assert r.json()["timezone"] == "Asia/Tbilisi"
    assert r.json()["full_name"] == "Nino"


async def test_workspace_timezone_must_be_iana(
    client: httpx.AsyncClient, queue: RecordingJobQueue
) -> None:
    await register_verified(client, queue, "wstz@example.com")
    ws = (await client.get("/workspaces")).json()[0]["id"]
    assert (
        await client.patch(f"/workspaces/{ws}", json={"timezone": "../../etc/passwd"})
    ).status_code == 422
    r = await client.patch(f"/workspaces/{ws}", json={"timezone": "Europe/Berlin"})
    assert r.status_code == 200
    assert r.json()["timezone"] == "Europe/Berlin"


def test_hosted_database_urls_are_normalised_for_asyncpg() -> None:
    from app.core.config import Settings

    def url(v: str) -> str:
        return Settings(DATABASE_URL=v, JWT_SECRET="x" * 40, SESSION_SECRET="y" * 40).DATABASE_URL

    neon = (
        "postgresql://u:p%40ss@ep-cool-1.eu-central-1.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require"
    )
    assert url(neon) == (
        "postgresql+asyncpg://u:p%40ss@ep-cool-1.eu-central-1.aws.neon.tech/neondb?ssl=require"
    )
    assert url("postgres://u:p@h:6543/db").startswith("postgresql+asyncpg://u:p@h:6543/db")
    local = "postgresql+asyncpg://cf:cf@localhost:5432/contentfactory"
    assert url(local) == local


def test_tests_never_read_the_developers_env_file() -> None:
    from app.core.config import Settings, settings

    # A developer's .env may hold real AI/payment keys; the suite must not pick them up.
    assert Settings.model_config["env_file"] is None
    assert settings.AI_PROVIDER == "mock" and settings.AI_EMBEDDING_PROVIDER == "local"


def _production(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ENVIRONMENT": "production",
        "JWT_SECRET": "x" * 40,
        "SESSION_SECRET": "y" * 40,
        "COOKIE_SECURE": True,
        "ENCRYPTION_KEYS": "k",
        "EMAIL_PROVIDER": "resend",
        "STORAGE_PROVIDER": "s3",
        "AI_PROVIDER": "gemini",
        "AI_PROVIDER_API_KEY": "key",
        "AI_FAST_MODEL": "f",
        "AI_REASONING_MODEL": "r",
        "AI_IMAGE_PROVIDER": "gemini",
        "AI_IMAGE_MODEL": "i",
    }
    base.update(overrides)
    return base


def test_production_refuses_unsafe_settings_and_allows_launch_without_billing() -> None:
    import pytest

    from app.billing import paddle
    from app.core.config import Settings

    with pytest.raises(ValueError, match="PADDLE"):
        Settings(**_production())  # type: ignore[arg-type]
    s = Settings(**_production(BILLING_ENABLED=False))  # type: ignore[arg-type]
    assert s.is_production and not s.BILLING_ENABLED
    for bad, match in [
        ({"COOKIE_SECURE": False}, "COOKIE_SECURE"),
        ({"STORAGE_PROVIDER": "local"}, "STORAGE_PROVIDER"),
        ({"EMAIL_PROVIDER": "console"}, "EMAIL_PROVIDER"),
        ({"AI_IMAGE_PROVIDER": "mock"}, "AI_IMAGE_PROVIDER"),
        ({"ENCRYPTION_KEYS": ""}, "ENCRYPTION_KEYS"),
    ]:
        with pytest.raises(ValueError, match=match):
            Settings(**_production(BILLING_ENABLED=False, **bad))  # type: ignore[arg-type]
    assert paddle.configured() is False  # no Paddle keys in tests
