"""Inventory: read-only browse for end users (no CRUD)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Item, ItemType
from app.models.enums import ItemStatus
from app.schemas.inventory import EventRead, InventorySummaryRow, ItemRead
from app.services.queries import distinct_locations_query, item_filter_query
from app.services.serialize import serialize_event, serialize_item

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("/items", response_model=list[ItemRead])
async def browse_items(
    q: str | None = None,
    type_id: uuid.UUID | None = None,
    location: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[ItemRead]:
    """Search/filter items. Read-only — there are no write routes in this module."""
    stmt = item_filter_query(q, type_id, location)
    items = list((await session.execute(stmt)).scalars().all())
    return [await serialize_item(session, item) for item in items]


@router.get("/items/{item_id}", response_model=ItemRead)
async def item_detail(item_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> ItemRead:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    return await serialize_item(session, item)


@router.get("/items/{item_id}/events", response_model=list[EventRead])
async def item_history(
    item_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[EventRead]:
    if await session.get(Item, item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    from app.models import Event

    result = await session.execute(
        select(Event).where(Event.item_id == item_id).order_by(Event.created_at.desc())
    )
    return [await serialize_event(session, e) for e in result.scalars().all()]


@router.get("/locations", response_model=list[str])
async def locations(session: AsyncSession = Depends(get_session)) -> list[str]:
    result = await session.execute(distinct_locations_query())
    return [row[0] for row in result.all()]


@router.get("/summary", response_model=list[InventorySummaryRow])
async def summary(session: AsyncSession = Depends(get_session)) -> list[InventorySummaryRow]:
    """Rollup of quantities per item type + location with availability counts."""
    types = {t.id: t.name for t in (await session.execute(select(ItemType))).scalars().all()}
    items = list((await session.execute(select(Item))).scalars().all())

    rows: dict[tuple[uuid.UUID, str | None], InventorySummaryRow] = {}
    for item in items:
        key = (item.item_type_id, item.location)
        row = rows.get(key)
        if row is None:
            row = InventorySummaryRow(
                item_type_id=item.item_type_id,
                item_type_name=types.get(item.item_type_id, "?"),
                location=item.location,
            )
            rows[key] = row
        row.total += 1
        serialized = await serialize_item(session, item)
        if serialized.status == ItemStatus.AVAILABLE:
            row.available += 1
        elif serialized.status == ItemStatus.ON_LOAN:
            row.on_loan += 1
    return sorted(rows.values(), key=lambda r: (r.item_type_name, r.location or ""))
