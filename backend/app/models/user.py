"""User: a person (typically a student) who can borrow items."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    # "user" is reserved in Postgres — use an explicit table name.
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    group_id: uuid.UUID | None = Field(default=None, foreign_key="groups.id", index=True)
    # Barcode encoded on the user's ID card. Unique so a scan resolves to one user.
    barcode: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
