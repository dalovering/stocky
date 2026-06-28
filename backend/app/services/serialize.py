"""Helpers that turn DB models into enriched read schemas (status, names, loans).

Centralized so every router presents items/users consistently.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item, ItemType, User
from app.models.enums import EventType
from app.models.event import Event
from app.schemas.inventory import EventRead, ItemRead
from app.schemas.user import UserDetail
from app.services.status import item_status, user_loan_item_ids


async def serialize_item(session: AsyncSession, item: Item) -> ItemRead:
    item_type = await session.get(ItemType, item.item_type_id)
    status, holder_id = await item_status(session, item)
    holder_name = None
    if holder_id is not None:
        holder = await session.get(User, holder_id)
        holder_name = holder.name if holder else None

    return ItemRead(
        id=item.id,
        item_type_id=item.item_type_id,
        name=item.name,
        # Photo/description fall back to the item type's values.
        photo_url=item.photo_url or (item_type.photo_url if item_type else None),
        description=item.description or (item_type.description if item_type else None),
        purchase_price=item.purchase_price,
        purchase_date=item.purchase_date,
        location=item.location,
        condition=item.condition,
        barcode=item.barcode,
        item_type_name=item_type.name if item_type else None,
        status=status,
        holder_user_id=holder_id,
        holder_name=holder_name,
    )


async def serialize_user_detail(session: AsyncSession, user: User) -> UserDetail:
    from app.models import Group

    group_name = None
    if user.group_id is not None:
        group = await session.get(Group, user.group_id)
        group_name = group.name if group else None

    loan_ids = await user_loan_item_ids(session, user.id)
    loans: list[ItemRead] = []
    for item_id in loan_ids:
        item = await session.get(Item, item_id)
        if item is not None:
            loans.append(await serialize_item(session, item))

    return UserDetail(
        id=user.id,
        name=user.name,
        group_id=user.group_id,
        group_name=group_name,
        barcode=user.barcode,
        loan_count=len(loans),
        current_loans=loans,
    )


async def serialize_event(session: AsyncSession, event: Event) -> EventRead:
    user_name = None
    if event.user_id is not None:
        user = await session.get(User, event.user_id)
        user_name = user.name if user else None
    return EventRead(
        id=event.id,
        item_id=event.item_id,
        user_id=event.user_id,
        user_name=user_name,
        event_type=event.event_type,
        note=event.note,
        created_at=event.created_at,
    )


async def loan_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Cheap-ish count of open loans (used in list views)."""
    return len(await user_loan_item_ids(session, user_id))


async def event_count_for_user(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Event)
        .where(Event.user_id == user_id, Event.event_type == EventType.CHECKOUT)
    )
    return int(result.scalar_one())
