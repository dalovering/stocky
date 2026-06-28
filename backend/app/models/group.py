"""Group: nestable container for users, with group-level permissions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Group(SQLModel, table=True):
    # "group" is a reserved SQL word — use an explicit, safe table name.
    __tablename__ = "groups"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    # Self-referential parent for nesting; null = top-level group.
    parent_id: uuid.UUID | None = Field(default=None, foreign_key="groups.id", index=True)
    # Flexible permission flags applied to members of this group.
    permissions: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
