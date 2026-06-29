"""Derive item status and user loans from the event log.

The `events` table is the source of truth. An item's current availability and a user's
current loans are *computed* from events (plus the item's stored condition), never stored
directly. Keeping this logic in one place ensures the kiosk, admin, and inventory views all
agree on what "on loan" means.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Condition, Event, EventType, Item, ItemStatus

# Events that close an open loan (the item is no longer in someone's hands).
_LOAN_CLOSING = {EventType.CHECKIN, EventType.LOSS_REPORT, EventType.DISCARD}


async def open_checkout_event(session: AsyncSession, item_id: uuid.UUID) -> Event | None:
    """Return the CHECKOUT event for the item's current open loan, or None if it isn't on loan.

    An item is on loan when its most recent loan-relevant event is a CHECKOUT.
    """
    result = await session.execute(
        select(Event)
        .where(
            Event.item_id == item_id,
            Event.event_type.in_([EventType.CHECKOUT, *_LOAN_CLOSING]),
        )
        .order_by(Event.created_at.desc(), Event.id.desc())
        .limit(1)
    )
    last = result.scalar_one_or_none()
    if last is not None and last.event_type == EventType.CHECKOUT:
        return last
    return None


async def latest_checkout_holder(session: AsyncSession, item_id: uuid.UUID) -> uuid.UUID | None:
    """Return the user_id currently holding the item, or None if it isn't on loan."""
    event = await open_checkout_event(session, item_id)
    return event.user_id if event is not None else None


async def checkout_started_at(session: AsyncSession, item_id: uuid.UUID) -> datetime | None:
    """When the item's current open loan began, or None if it isn't on loan."""
    event = await open_checkout_event(session, item_id)
    return event.created_at if event is not None else None


async def item_status(session: AsyncSession, item: Item) -> tuple[ItemStatus, uuid.UUID | None]:
    """Compute (status, holder_user_id) for an item.

    Terminal conditions (Discarded, Lost) win. Otherwise an open checkout means On loan;
    a Damaged condition with no open loan means Damaged; everything else is Available.
    """
    if item.condition == Condition.DISCARDED:
        return ItemStatus.DISCARDED, None
    if item.condition == Condition.LOST:
        return ItemStatus.LOST, None

    holder = await latest_checkout_holder(session, item.id)
    if holder is not None:
        return ItemStatus.ON_LOAN, holder
    if item.condition == Condition.DAMAGED:
        return ItemStatus.DAMAGED, None
    return ItemStatus.AVAILABLE, None


async def user_loan_item_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Return the set of item ids currently checked out by the given user."""
    # All items this user has ever checked out...
    result = await session.execute(
        select(Event.item_id)
        .where(Event.user_id == user_id, Event.event_type == EventType.CHECKOUT)
        .distinct()
    )
    candidate_ids = {row[0] for row in result.all()}

    held: set[uuid.UUID] = set()
    for item_id in candidate_ids:
        if await latest_checkout_holder(session, item_id) == user_id:
            held.add(item_id)
    return held
