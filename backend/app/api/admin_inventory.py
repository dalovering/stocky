"""Admin: inventory management — item types and items (CRUD, history, barcodes)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_session
from app.models import Event, EventType, Item, ItemType
from app.schemas.inventory import (
    EventRead,
    ItemCreate,
    ItemRead,
    ItemTypeCreate,
    ItemTypeRead,
    ItemTypeUpdate,
    ItemUpdate,
)
from app.services import barcode as barcode_svc
from app.services.serialize import serialize_event, serialize_item

router = APIRouter(
    prefix="/api/admin", tags=["admin:inventory"], dependencies=[Depends(require_admin)]
)


# ---------------------------------------------------------------------------
# Passive multi-select lookups (distinct values for "add new" dropdowns)
# ---------------------------------------------------------------------------
@router.get("/locations", response_model=list[str])
async def list_locations(session: AsyncSession = Depends(get_session)) -> list[str]:
    result = await session.execute(
        select(distinct(Item.location)).where(Item.location.is_not(None)).order_by(Item.location)
    )
    return [row[0] for row in result.all()]


@router.get("/manufacturers", response_model=list[str])
async def list_manufacturers(session: AsyncSession = Depends(get_session)) -> list[str]:
    result = await session.execute(
        select(distinct(ItemType.manufacturer))
        .where(ItemType.manufacturer.is_not(None))
        .order_by(ItemType.manufacturer)
    )
    return [row[0] for row in result.all()]


# ---------------------------------------------------------------------------
# Item types
# ---------------------------------------------------------------------------
@router.get("/item-types", response_model=list[ItemTypeRead])
async def list_item_types(
    q: str | None = None, session: AsyncSession = Depends(get_session)
) -> list[ItemTypeRead]:
    stmt = select(ItemType)
    if q:
        stmt = stmt.where(ItemType.name.ilike(f"%{q}%"))
    types = list((await session.execute(stmt.order_by(ItemType.name))).scalars().all())
    counts = dict(
        (
            await session.execute(
                select(Item.item_type_id, func.count()).group_by(Item.item_type_id)
            )
        ).all()
    )
    return [ItemTypeRead(**t.model_dump(), item_count=int(counts.get(t.id, 0))) for t in types]


@router.post("/item-types", response_model=ItemTypeRead, status_code=status.HTTP_201_CREATED)
async def create_item_type(
    body: ItemTypeCreate, session: AsyncSession = Depends(get_session)
) -> ItemTypeRead:
    item_type = ItemType(**body.model_dump())
    session.add(item_type)
    await session.commit()
    await session.refresh(item_type)
    return ItemTypeRead(**item_type.model_dump(), item_count=0)


@router.patch("/item-types/{type_id}", response_model=ItemTypeRead)
async def update_item_type(
    type_id: uuid.UUID, body: ItemTypeUpdate, session: AsyncSession = Depends(get_session)
) -> ItemTypeRead:
    item_type = await session.get(ItemType, type_id)
    if item_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item type not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item_type, field, value)
    session.add(item_type)
    await session.commit()
    await session.refresh(item_type)
    count = await session.scalar(
        select(func.count()).select_from(Item).where(Item.item_type_id == type_id)
    )
    return ItemTypeRead(**item_type.model_dump(), item_count=int(count or 0))


@router.delete("/item-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item_type(
    type_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> None:
    item_type = await session.get(ItemType, type_id)
    if item_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item type not found.")
    count = await session.scalar(
        select(func.count()).select_from(Item).where(Item.item_type_id == type_id)
    )
    if count:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Cannot delete an item type that still has items."
        )
    await session.delete(item_type)
    await session.commit()


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------
async def _unique_item_barcode(session: AsyncSession, proposed: str | None) -> str:
    if proposed:
        existing = await session.execute(select(Item).where(Item.barcode == proposed))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Barcode already in use.")
        return proposed
    for _ in range(10):
        code = barcode_svc.generate_item_code()
        existing = await session.execute(select(Item).where(Item.barcode == code))
        if existing.scalar_one_or_none() is None:
            return code
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not allocate a barcode.")


@router.get("/items", response_model=list[ItemRead])
async def list_items(
    q: str | None = None,
    type_id: uuid.UUID | None = None,
    location: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[ItemRead]:
    stmt = select(Item)
    if type_id is not None:
        stmt = stmt.where(Item.item_type_id == type_id)
    if location:
        stmt = stmt.where(Item.location == location)
    if q:
        stmt = stmt.where(Item.name.ilike(f"%{q}%"))
    items = list((await session.execute(stmt.order_by(Item.name))).scalars().all())
    return [await serialize_item(session, item) for item in items]


@router.post("/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(body: ItemCreate, session: AsyncSession = Depends(get_session)) -> ItemRead:
    item_type = await session.get(ItemType, body.item_type_id)
    if item_type is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown item type.")
    barcode = await _unique_item_barcode(session, body.barcode)
    data = body.model_dump(exclude={"barcode"})
    item = Item(**data, barcode=barcode)
    session.add(item)
    await session.flush()
    # Record creation in the event log so history is complete.
    session.add(Event(item_id=item.id, event_type=EventType.CREATE))
    await session.commit()
    await session.refresh(item)
    return await serialize_item(session, item)


@router.get("/items/{item_id}", response_model=ItemRead)
async def get_item(item_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> ItemRead:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    return await serialize_item(session, item)


@router.patch("/items/{item_id}", response_model=ItemRead)
async def update_item(
    item_id: uuid.UUID, body: ItemUpdate, session: AsyncSession = Depends(get_session)
) -> ItemRead:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return await serialize_item(session, item)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    # Remove history first to satisfy the FK.
    for event in (
        (await session.execute(select(Event).where(Event.item_id == item_id))).scalars().all()
    ):
        await session.delete(event)
    await session.delete(item)
    await session.commit()


@router.get("/items/{item_id}/events", response_model=list[EventRead])
async def item_events(
    item_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[EventRead]:
    result = await session.execute(
        select(Event).where(Event.item_id == item_id).order_by(Event.created_at.desc())
    )
    return [await serialize_event(session, e) for e in result.scalars().all()]


@router.get("/items/{item_id}/barcode.svg")
async def item_barcode_svg(
    item_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    return Response(content=barcode_svc.render_svg(item.barcode), media_type="image/svg+xml")
