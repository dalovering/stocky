"""Item: an individual, trackable physical unit of an ItemType."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlmodel import Field, SQLModel

from app.models.common import timestamp_column, utcnow
from app.models.enums import Condition


class Item(SQLModel, table=True):
    __tablename__ = "items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    item_type_id: uuid.UUID = Field(foreign_key="item_types.id", index=True)
    name: str = Field(index=True)
    # Photo/description default to the item type's when null (resolved in the API layer).
    photo_url: str | None = None
    description: str | None = None
    purchase_price: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    purchase_date: date | None = None
    location: str | None = Field(default=None, index=True)
    condition: Condition = Field(default=Condition.NEW)
    # Barcode on the physical item / its printed tag. Unique so a scan resolves to one item.
    barcode: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
