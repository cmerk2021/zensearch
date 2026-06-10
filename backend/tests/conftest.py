"""Shared test fixtures.

Environment is forced to ``test`` before any zen import so configuration,
caching and database state are fully isolated per test.
"""

from __future__ import annotations

import os

os.environ["ZEN_ENV"] = "test"
os.environ["ZEN_SECRET_KEY"] = "test-secret-key-for-the-zen-test-suite-0123456789"
os.environ["ZEN_RATE_LIMIT_ENABLED"] = "true"
os.environ.pop("ZEN_REDIS_URL", None)
os.environ.pop("ZEN_DATABASE_URL", None)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from zen.core.cache import MemoryCache, set_cache
from zen.core.config import reset_settings_cache
from zen.db import base as db_base
from zen.services import settings as settings_module


@pytest_asyncio.fixture
async def app(tmp_path, monkeypatch):
    """A fully initialised Zen app backed by a throwaway SQLite database."""
    db_path = tmp_path / "zen-test.db"
    monkeypatch.setenv("ZEN_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ZEN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ZEN_PLUGINS_DIR", str(tmp_path / "plugins"))

    reset_settings_cache()
    set_cache(MemoryCache())
    settings_module.SettingsService.invalidate_local()

    await db_base.dispose_engine()
    db_base.init_db(f"sqlite+aiosqlite:///{db_path}")
    await db_base.create_all()

    factory = db_base.get_session_factory()
    async with factory() as db:
        from zen.services.bootstrap import bootstrap_instance

        await bootstrap_instance(db)

    from zen.main import create_app

    application = create_app()
    yield application

    await db_base.dispose_engine()
    set_cache(None)
    reset_settings_cache()
    settings_module.SettingsService.invalidate_local()


@pytest_asyncio.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://zen.test") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def db_session(app):
    factory = db_base.get_session_factory()
    async with factory() as session:
        yield session


async def create_user(
    role: str = "user", username: str | None = None, password: str = "sufficiently-long-pw-1"
):
    from zen.services.auth import AuthService

    factory = db_base.get_session_factory()
    async with factory() as db:
        auth = AuthService(db)
        name = username or f"{role}-tester"
        user = await auth.create_user(username=name, password=password, role=role)
        return user


async def login(client: AsyncClient, username: str, password: str = "sufficiently-long-pw-1"):
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    csrf = response.json()["csrf_token"]
    client.headers["X-CSRF-Token"] = csrf
    return response.json()["user"]


@pytest_asyncio.fixture
async def user_client(app, client) -> AsyncClient:
    await create_user("user", "alice")
    await login(client, "alice")
    return client


@pytest_asyncio.fixture
async def admin_client(app) -> AsyncClient:
    await create_user("admin", "root-admin")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://zen.test") as admin_http:
        await login(admin_http, "root-admin")
        yield admin_http


@pytest_asyncio.fixture
async def readonly_client(app) -> AsyncClient:
    await create_user("readonly", "viewer")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://zen.test") as ro_http:
        await login(ro_http, "viewer")
        yield ro_http


# Re-export helpers for test modules.
__all__ = ["create_user", "login"]
