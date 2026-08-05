"""User: a person (typically a student) who can borrow items."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String
from sqlmodel import Field, SQLModel

from app.models.common import timestamp_column, utcnow
from app.models.enums import UserStatus


class User(SQLModel, table=True):
    # "user" is reserved in Postgres — use an explicit table name.
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    group_id: uuid.UUID | None = Field(default=None, foreign_key="groups.id", index=True)
    # Lifecycle state; stored as VARCHAR so the vocabulary can change without a DB migration.
    status: UserStatus = Field(default=UserStatus.ACTIVE, sa_type=String, nullable=False)
    # Barcode encoded on the user's ID card. Unique so a scan resolves to one user.
    barcode: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
