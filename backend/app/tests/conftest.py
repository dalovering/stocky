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
from app.core.db import get_session
from app.main import app

TEST_ADMIN_PASSWORD = "test-admin-password"


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
