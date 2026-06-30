"""Admin: inventory management — item types and items (CRUD, history, barcodes)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_unique_barcode, require_admin
from app.core.db import get_session
from app.models import Event, EventType, Item, ItemStatus, ItemType
from app.schemas.inventory import (
    EventRead,
    IdList,
    ItemBatchStatusChange,
    ItemBatchUpdate,
    ItemCreate,
    ItemRead,
    ItemStatusChange,
    ItemTypeCreate,
    ItemTypeRead,
    ItemTypeUpdate,
    ItemUpdate,
)
from app.services import barcode as barcode_svc
from app.services import events as event_svc
from app.services.queries import distinct_locations_query, item_filter_query
from app.services.serialize import serialize_event, serialize_item, serialize_items_bulk

router = APIRouter(
    prefix="/api/admin", tags=["admin:inventory"], dependencies=[Depends(require_admin)]
)


# ---------------------------------------------------------------------------
# Passive multi-select lookups (distinct values for "add new" dropdowns)
# ---------------------------------------------------------------------------
@router.get("/locations", response_model=list[str])
async def list_locations(session: AsyncSession = Depends(get_session)) -> list[str]:
    result = await session.execute(distinct_locations_query())
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
    return await ensure_unique_barcode(session, Item, barcode_svc.ITEM_PREFIX, proposed)


@router.get("/items", response_model=list[ItemRead])
async def list_items(
    q: str | None = None,
    type_id: uuid.UUID | None = None,
    location: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[ItemRead]:
    stmt = item_filter_query(q, type_id, location)
    items = list((await session.execute(stmt)).scalars().all())
    return await serialize_items_bulk(session, items)


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


# ---------------------------------------------------------------------------
# Batch & status operations
#
# Defined before the `/items/{item_id}` routes so the literal "batch" segment is matched
# first (otherwise "batch" would be parsed as a UUID item id and 422).
# ---------------------------------------------------------------------------
# Admin status -> the availability event that produces it. "Checked out" is loan-driven, not
# directly settable.
_STATUS_ACTIONS = {
    ItemStatus.AVAILABLE: event_svc.restore,
    ItemStatus.UNAVAILABLE: event_svc.mark_unavailable,
    ItemStatus.LOST: event_svc.mark_lost,
    ItemStatus.DISCARDED: event_svc.discard,
}


async def _apply_item_status(
    session: AsyncSession, item: Item, new_status: ItemStatus, note: str | None
) -> None:
    action = _STATUS_ACTIONS.get(new_status)
    if action is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{new_status} is determined by check-in/out and can't be set directly.",
        )
    await action(session, item, note)


async def _items_by_ids(session: AsyncSession, ids: list[uuid.UUID]) -> list[Item]:
    if not ids:
        return []
    return list((await session.execute(select(Item).where(Item.id.in_(ids)))).scalars().all())


@router.post("/items/batch/status", response_model=list[ItemRead])
async def batch_set_item_status(
    body: ItemBatchStatusChange, session: AsyncSession = Depends(get_session)
) -> list[ItemRead]:
    items = await _items_by_ids(session, body.ids)
    for item in items:
        await _apply_item_status(session, item, body.status, body.note)
    await session.commit()
    return await serialize_items_bulk(session, items)


@router.patch("/items/batch", response_model=list[ItemRead])
async def batch_update_items(
    body: ItemBatchUpdate, session: AsyncSession = Depends(get_session)
) -> list[ItemRead]:
    data = body.patch.model_dump(exclude_unset=True)
    items = await _items_by_ids(session, body.ids)
    for item in items:
        for field, value in data.items():
            setattr(item, field, value)
        session.add(item)
    await session.commit()
    return await serialize_items_bulk(session, items)


@router.post("/items/batch-delete", status_code=status.HTTP_204_NO_CONTENT)
async def batch_delete_items(body: IdList, session: AsyncSession = Depends(get_session)) -> None:
    if body.ids:
        # Remove history first to satisfy the events -> items foreign key.
        await session.execute(delete(Event).where(Event.item_id.in_(body.ids)))
        await session.execute(delete(Item).where(Item.id.in_(body.ids)))
        await session.commit()


@router.post("/items/{item_id}/status", response_model=ItemRead)
async def set_item_status(
    item_id: uuid.UUID, body: ItemStatusChange, session: AsyncSession = Depends(get_session)
) -> ItemRead:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    await _apply_item_status(session, item, body.status, body.note)
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
