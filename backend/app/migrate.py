"""Bring any database — including an empty one — to schema head.

`alembic upgrade head` alone cannot handle a FRESH database here: the baseline
migration (0001) is a live `SQLModel.metadata.create_all`, so it builds the *current*
schema, and every later migration then re-applies a change the baseline already made
(0002's `groups.semester_start` → DuplicateColumn on every fresh install). Replaying
history is impossible when the first step always jumps straight to HEAD.

So fresh databases don't replay history: `create_all` builds the current schema and the
migration chain is *stamped* as applied. Databases that have migrated before upgrade
normally. This keeps every migration file untouched (the alternative — freezing 0001
into explicit DDL — means editing a migration already in history, which the project
forbids). A database that has tables but no `alembic_version` is an unknown state and
is refused rather than guessed at.

Used by `make migrate`; also runs in-container:
    uv run python -m app.migrate
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

import app.models  # noqa: F401  (register tables on metadata)
from alembic import command
from app.core.config import settings

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    # env.py prefers this over the app settings, so tests (and this script) can point
    # alembic at an explicit database.
    cfg.attributes["database_url"] = database_url
    return cfg


async def _db_state(database_url: str) -> tuple[bool, bool]:
    """(has alembic_version, has any app table) — decides bootstrap vs upgrade."""
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:

            def look(sync_conn) -> tuple[bool, bool]:
                existing = set(inspect(sync_conn).get_table_names())
                app_tables = set(SQLModel.metadata.tables)
                return "alembic_version" in existing, bool(existing & app_tables)

            return await conn.run_sync(look)
    finally:
        await engine.dispose()


async def _create_all(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    finally:
        await engine.dispose()


class UnknownDatabaseState(RuntimeError):
    """Tables exist but alembic has never run — refuse to guess."""


def bootstrap(database_url: str) -> str:
    """Bring the database to schema head; returns "upgraded" or "bootstrapped"."""
    versioned, has_tables = asyncio.run(_db_state(database_url))
    cfg = alembic_config(database_url)
    if versioned:
        command.upgrade(cfg, "head")
        return "upgraded"
    if has_tables:
        raise UnknownDatabaseState(
            "The database has tables but no alembic_version — it predates migrations "
            "or was created outside them. Refusing to guess; if this schema is in fact "
            "current, `alembic stamp head` records that, then re-run."
        )
    asyncio.run(_create_all(database_url))
    command.stamp(cfg, "head")
    return "bootstrapped"


def main() -> int:
    try:
        action = bootstrap(settings.database_url)
    except UnknownDatabaseState as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if action == "bootstrapped":
        print("Fresh database: created the current schema and stamped the migration head.")
    else:
        print("Applied pending migrations (alembic upgrade head).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
