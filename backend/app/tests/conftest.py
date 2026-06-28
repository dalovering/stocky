"""Pytest fixtures: an in-memory SQLite DB and an authenticated test client.

Tests run against SQLite (fast, no external service) since the models use cross-dialect
types. The schema is created from the SQLModel metadata — the same source the baseline
Alembic migration uses.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

import app.models  # noqa: F401  (register tables on metadata)
from app.core.config import settings
from app.core.db import get_session
from app.main import app


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    """A client with a valid admin session cookie."""
    resp = await client.post("/api/auth/login", json={"password": settings.admin_password})
    assert resp.status_code == 200, resp.text
    return client
