"""Fresh-install migration bootstrap, against a real postgres:18.

The bug this pins: the baseline migration is a live `create_all`, so a fresh database
that tries to REPLAY the chain dies when 0002 re-adds a column the baseline already
built (`groups.semester_start`). `app.migrate` must therefore bootstrap+stamp an empty
database, upgrade a versioned one, and refuse an unversioned one with tables.

These tests are sync on purpose: alembic's env.py calls `asyncio.run`, which cannot be
nested inside a pytest-asyncio event loop.
"""

from __future__ import annotations

import asyncio

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from app.migrate import UnknownDatabaseState, alembic_config, bootstrap


def _run(coro):
    return asyncio.run(coro)


async def _tables(url: str) -> set[str]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    finally:
        await engine.dispose()


async def _stamped_revision(url: str) -> str | None:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            row = await conn.execute(text("SELECT version_num FROM alembic_version"))
            return row.scalar_one_or_none()
    finally:
        await engine.dispose()


async def _wipe(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    finally:
        await engine.dispose()


async def _create_all_only(url: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    finally:
        await engine.dispose()


@pytest.fixture
def clean_db(postgres_url: str):
    """A genuinely empty database, cleaned up again afterwards (alembic_version is not
    on the app metadata, so the other fixtures' drop_all never removes it)."""
    _run(_wipe(postgres_url))
    yield postgres_url
    _run(_wipe(postgres_url))


def test_fresh_database_bootstraps_to_head(clean_db: str) -> None:
    assert bootstrap(clean_db) == "bootstrapped"
    head = ScriptDirectory.from_config(alembic_config(clean_db)).get_current_head()
    assert _run(_stamped_revision(clean_db)) == head
    tables = _run(_tables(clean_db))
    assert {"users", "groups", "items", "item_types", "events", "settings"} <= tables


def test_bootstrapped_database_then_upgrades_as_noop(clean_db: str) -> None:
    bootstrap(clean_db)
    assert bootstrap(clean_db) == "upgraded"  # versioned now; plain no-op upgrade path


def test_tables_without_alembic_version_are_refused(clean_db: str) -> None:
    _run(_create_all_only(clean_db))  # schema exists, but alembic never ran
    with pytest.raises(UnknownDatabaseState, match="alembic stamp head"):
        bootstrap(clean_db)
    # And it changed nothing: still unversioned.
    assert "alembic_version" not in _run(_tables(clean_db))
