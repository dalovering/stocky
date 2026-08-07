"""Pytest fixtures: a REAL postgres:18 database and an authenticated test client.

Tests run against a genuine PostgreSQL 18 container (via testcontainers) — never SQLite.
This guarantees the schema, column types (tz-aware timestamps, JSON, UUID), and queries are
exercised exactly as in production. Requires a running Docker daemon.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from testcontainers.postgres import PostgresContainer

import app.models  # noqa: F401  (register tables on metadata)
from app.core.config import settings as app_config
from app.core.db import get_session
from app.main import app

TEST_ADMIN_PASSWORD = "test-admin-password"


@pytest.fixture(autouse=True)
def _printer_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin printer config to the class defaults for every test.

    `Settings` reads `.env`, so a developer with a real printer configured
    (PRINTER_DEVICE=/dev/usb/lp0) would otherwise fail the tests that assume an
    unconfigured printer. Tests that need a device set one explicitly via monkeypatch,
    which happens after this and wins.
    """
    monkeypatch.setattr(app_config, "printer_device", "")
    monkeypatch.setattr(app_config, "printer_transport", "auto")
    monkeypatch.setattr(app_config, "printer_baud", 115200)
    monkeypatch.setattr(app_config, "printer_bitmap_mode", 1)


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Start one postgres:18 container for the whole test session; yield an asyncpg URL."""
    with PostgresContainer("postgres:18", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest_asyncio.fixture
async def session(postgres_url: str) -> AsyncGenerator[AsyncSession]:
    """Fresh schema per test (create_all/drop_all) for isolation, on the real database."""
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as s:
            yield s
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    """A client with a valid admin session cookie (runs first-launch setup to get one)."""
    resp = await client.post("/api/auth/setup", json={"password": TEST_ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return client
