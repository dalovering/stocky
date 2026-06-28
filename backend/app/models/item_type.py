"""ItemType: a template/catalog entry that individual Items are instances of."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel

from app.models.common import timestamp_column, utcnow


class ItemType(SQLModel, table=True):
    __tablename__ = "item_types"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    manufacturer: str | None = Field(default=None, index=True)
    author: str | None = None
    publish_date: date | None = None
    description: str | None = None
    photo_url: str | None = None
    url: str | None = None
    cost: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    upc_isbn: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
