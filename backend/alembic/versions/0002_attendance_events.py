"""Attendance events: nullable events.item_id + groups.semester_start.

Attendance is a user-only event (no item), so `events.item_id` loosens to nullable — the FK,
index, and every existing row are untouched. `groups.semester_start` is a nullable DATE holding
the start of the "since semester start" attendance window; no backfill needed.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("events", "item_id", existing_type=sa.Uuid(), nullable=True)
    op.add_column("groups", sa.Column("semester_start", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("groups", "semester_start")
    # Attendance rows have no item; they cannot survive re-tightening the constraint.
    op.execute("DELETE FROM events WHERE item_id IS NULL")
    op.alter_column("events", "item_id", existing_type=sa.Uuid(), nullable=False)
