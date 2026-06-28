from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import Condition, EventType, ItemStatus

# ---------------------------------------------------------------------------
# Item types
# ---------------------------------------------------------------------------


class ItemTypeCreate(BaseModel):
    name: str
    manufacturer: str | None = None
    author: str | None = None
    publish_date: date | None = None
    description: str | None = None
    photo_url: str | None = None
    url: str | None = None
    cost: Decimal | None = None
    upc_isbn: str | None = None


class ItemTypeUpdate(BaseModel):
    name: str | None = None
    manufacturer: str | None = None
    author: str | None = None
    publish_date: date | None = None
    description: str | None = None
    photo_url: str | None = None
    url: str | None = None
    cost: Decimal | None = None
    upc_isbn: str | None = None


class ItemTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    manufacturer: str | None
    author: str | None
    publish_date: date | None
    description: str | None
    photo_url: str | None
    url: str | None
    cost: Decimal | None
    upc_isbn: str | None
    item_count: int = 0


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


class ItemCreate(BaseModel):
    item_type_id: uuid.UUID
    name: str
    photo_url: str | None = None
    description: str | None = None
    purchase_price: Decimal | None = None
    purchase_date: date | None = None
    location: str | None = None
    condition: Condition = Condition.NEW
    # Optional explicit barcode; generated if omitted.
    barcode: str | None = None


class ItemUpdate(BaseModel):
    item_type_id: uuid.UUID | None = None
    name: str | None = None
    photo_url: str | None = None
    description: str | None = None
    purchase_price: Decimal | None = None
    purchase_date: date | None = None
    location: str | None = None
    condition: Condition | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_type_id: uuid.UUID
    name: str
    photo_url: str | None
    description: str | None
    purchase_price: Decimal | None
    purchase_date: date | None
    location: str | None
    condition: Condition
    barcode: str
    # Derived/enriched fields:
    item_type_name: str | None = None
    status: ItemStatus = ItemStatus.AVAILABLE
    holder_user_id: uuid.UUID | None = None
    holder_name: str | None = None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    user_id: uuid.UUID | None
    user_name: str | None = None
    event_type: EventType
    note: str | None
    created_at: datetime


class InventorySummaryRow(BaseModel):
    """One row of the read-only inventory rollup: counts per type/location."""

    item_type_id: uuid.UUID
    item_type_name: str
    location: str | None = None
    total: int = 0
    available: int = 0
    on_loan: int = 0
