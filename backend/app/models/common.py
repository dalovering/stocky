"""Shared model helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime


def utcnow() -> datetime:
    """Timezone-aware current UTC time (used for created_at defaults)."""
    return datetime.now(UTC)


def timestamp_column(*, index: bool = False) -> Column:
    """A `TIMESTAMP WITH TIME ZONE` column.

    Postgres rejects storing tz-aware datetimes in a naive column, so timestamps are stored
    tz-aware. Build a fresh Column per call (SQLAlchemy columns can't be shared across models).
    """
    return Column(DateTime(timezone=True), nullable=False, index=index)
