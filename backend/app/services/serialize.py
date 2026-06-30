"""Helpers that turn DB models into enriched read schemas (status, names, loans).

Centralized so every router presents items/users consistently.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Item, ItemStatus, ItemType, User
from app.models.enums import EventType
from app.models.event import Event
from app.schemas.inventory import EventRead, ItemRead
from app.schemas.user import UserDetail
from app.services.status import (
    _AVAILABILITY_EVENTS,
    _AVAILABILITY_STATUS,
    _LOAN_CLOSING,
    checkout_started_at,
    combine_status,
    item_status,
    user_loan_item_ids,
)


async def serialize_item(session: AsyncSession, item: Item) -> ItemRead:
    item_type = await session.get(ItemType, item.item_type_id)
    status, holder_id = await item_status(session, item)
    holder_name = None
    checked_out_at = None
    if holder_id is not None:
        holder = await session.get(User, holder_id)
        holder_name = holder.name if holder else None
        checked_out_at = await checkout_started_at(session, item.id)

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
        needs_review=item.needs_review,
        barcode=item.barcode,
        item_type_name=item_type.name if item_type else None,
        status=status,
        holder_user_id=holder_id,
        holder_name=holder_name,
        checked_out_at=checked_out_at,
    )


async def serialize_items_bulk(session: AsyncSession, items: list[Item]) -> list[ItemRead]:
    """Serialize a list of items with a bounded number of queries (no per-item N+1).

    Resolves item-type names, sticky availability, and the current loan holder in a few batched
    queries using `DISTINCT ON (events.item_id)` for the "latest event per item" lookups. Use this
    for list endpoints; `serialize_item` stays for single-item paths.
    """
    if not items:
        return []
    item_ids = [i.id for i in items]

    type_ids = {i.item_type_id for i in items}
    types = {
        t.id: t
        for t in (
            await session.execute(select(ItemType).where(ItemType.id.in_(type_ids)))
        ).scalars()
    }

    # Latest availability event per item -> sticky status.
    avail_rows = (
        await session.execute(
            select(Event)
            .where(Event.item_id.in_(item_ids), Event.event_type.in_(_AVAILABILITY_EVENTS))
            .order_by(Event.item_id, Event.created_at.desc(), Event.id.desc())
            .distinct(Event.item_id)
        )
    ).scalars()
    sticky: dict[uuid.UUID, ItemStatus] = {
        e.item_id: _AVAILABILITY_STATUS[EventType(e.event_type)] for e in avail_rows
    }

    # Latest loan-relevant event per item -> open loan when it's a CHECKOUT.
    loan_rows = (
        await session.execute(
            select(Event)
            .where(
                Event.item_id.in_(item_ids),
                Event.event_type.in_([EventType.CHECKOUT, *_LOAN_CLOSING]),
            )
            .order_by(Event.item_id, Event.created_at.desc(), Event.id.desc())
            .distinct(Event.item_id)
        )
    ).scalars()
    open_loans: dict[uuid.UUID, Event] = {
        e.item_id: e for e in loan_rows if EventType(e.event_type) == EventType.CHECKOUT
    }

    holder_ids = {e.user_id for e in open_loans.values() if e.user_id is not None}
    holders = (
        {
            u.id: u.name
            for u in (await session.execute(select(User).where(User.id.in_(holder_ids)))).scalars()
        }
        if holder_ids
        else {}
    )

    out: list[ItemRead] = []
    for item in items:
        item_type = types.get(item.item_type_id)
        sticky_status = sticky.get(item.id, ItemStatus.AVAILABLE)
        loan = open_loans.get(item.id)
        holder_id = loan.user_id if loan is not None else None
        status, holder = combine_status(sticky_status, holder_id)
        checked_out_at = loan.created_at if (loan is not None and holder is not None) else None
        out.append(
            ItemRead(
                id=item.id,
                item_type_id=item.item_type_id,
                name=item.name,
                photo_url=item.photo_url or (item_type.photo_url if item_type else None),
                description=item.description or (item_type.description if item_type else None),
                purchase_price=item.purchase_price,
                purchase_date=item.purchase_date,
                location=item.location,
                condition=item.condition,
                needs_review=item.needs_review,
                barcode=item.barcode,
                item_type_name=item_type.name if item_type else None,
                status=status,
                holder_user_id=holder,
                holder_name=holders.get(holder) if holder else None,
                checked_out_at=checked_out_at,
            )
        )
    return out


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
    item = await session.get(Item, event.item_id)
    return EventRead(
        id=event.id,
        item_id=event.item_id,
        item_name=item.name if item else None,
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
