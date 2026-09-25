"""Test harness: real PostgreSQL (migrated with Alembic), fake Redis, recording job queue."""

from __future__ import annotations

import os

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": os.environ.get(
            "TEST_DATABASE_URL", "postgresql+asyncpg://cf:cf@localhost:5432/contentfactory_test"
        ),
        "JWT_SECRET": "test-jwt-secret-0123456789abcdef0123456789",
        "SESSION_SECRET": "test-session-secret-0123456789abcdef012345",
        "COOKIE_SECURE": "0",
        "AUTH_REQUIRE_EMAIL_VERIFICATION": "1",
        "AUTH_GOOGLE_ENABLED": "0",
        "CORS_ORIGINS": "http://testserver",
        "APP_URL": "http://testserver",
    }
)

import subprocess  # noqa: E402
import sys  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402

import fakeredis  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.core.redis import set_redis  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.workers.queue import RecordingJobQueue, set_queue  # noqa: E402

PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    env = {**os.environ}
    for args in (["downgrade", "base"], ["upgrade", "head"]):
        subprocess.run(
            [sys.executable, "-m", "alembic", *args], check=True, env=env, capture_output=True
        )


@pytest.fixture(autouse=True)
async def clean_state() -> AsyncIterator[None]:
    set_redis(fakeredis.FakeAsyncRedis(decode_responses=True))
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def queue() -> RecordingJobQueue:
    q = RecordingJobQueue()
    set_queue(q)
    return q


@pytest.fixture
def no_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AUTH_REQUIRE_EMAIL_VERIFICATION", False)


def _client() -> httpx.AsyncClient:
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver/api/v1"
    )

    async def add_csrf(request: httpx.Request) -> None:
        token = client.cookies.get("cf_csrf")
        if token and request.method not in ("GET", "HEAD", "OPTIONS"):
            request.headers["x-csrf-token"] = token

    client.event_hooks["request"].append(add_csrf)
    return client


@pytest.fixture
async def client(queue: RecordingJobQueue) -> AsyncIterator[httpx.AsyncClient]:
    async with _client() as c:
        await c.get("/auth/csrf")
        yield c


@pytest.fixture
def make_client(queue: RecordingJobQueue):  # type: ignore[no-untyped-def]
    """Factory for extra independent browsers (other users / other devices)."""
    opened: list[httpx.AsyncClient] = []

    async def _make() -> httpx.AsyncClient:
        c = _client()
        opened.append(c)
        await c.get("/auth/csrf")
        return c

    yield _make


async def register_verified(
    client: httpx.AsyncClient, queue: RecordingJobQueue, email: str, name: str = "Nino"
) -> dict:
    r = await client.post(
        "/auth/register", json={"email": email, "password": PASSWORD, "full_name": name}
    )
    assert r.status_code == 201, r.text
    token = queue.last("send_email")["params"]["token"]
    r = await client.post("/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(autouse=True)
def storage(tmp_path):  # type: ignore[no-untyped-def]
    """Every test gets an isolated on-disk object store."""
    from app.storage import set_storage
    from app.storage.local import LocalStorage

    store = LocalStorage(tmp_path / "storage")
    set_storage(store)
    yield store
    set_storage(None)
