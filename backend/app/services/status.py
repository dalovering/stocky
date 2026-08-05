"""Derive item status and user loans from the event log.

The `events` table is the source of truth. An item's current availability and a user's
current loans are *computed* from events, never stored directly. Keeping this logic in one
place ensures the kiosk, admin, and inventory views all agree on what "on loan" means.

Two independent concerns combine into the single derived `ItemStatus`:

* **Loan state** — Checked out vs Available — from the check-in/out chain (`_LOAN_CLOSING`).
* **Sticky availability** — Unavailable / Lost / Discarded — from the latest "availability"
  event (`_AVAILABILITY_EVENTS`): a damage/loss report or an explicit admin Mark/Restore. A
  check-in does *not* clear sticky availability, so an item returned damaged stays Unavailable
  until an admin Restores it.

Priority: Discarded > Lost > Checked out > Unavailable > Available.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventType, Item, ItemStatus

# Events that close an open loan (the item is no longer in someone's hands).
_LOAN_CLOSING = {EventType.CHECKIN, EventType.LOSS_REPORT, EventType.DISCARD}

# Events that set an item's "sticky" availability (the latest one wins).
_AVAILABILITY_EVENTS = {
    EventType.DAMAGE_REPORT,
    EventType.LOSS_REPORT,
    EventType.DISCARD,
    EventType.MARK_UNAVAILABLE,
    EventType.RESTORE,
}

# How each availability event maps to a sticky status. RESTORE clears back to Available.
_AVAILABILITY_STATUS = {
    EventType.DAMAGE_REPORT: ItemStatus.UNAVAILABLE,
    EventType.MARK_UNAVAILABLE: ItemStatus.UNAVAILABLE,
    EventType.LOSS_REPORT: ItemStatus.LOST,
    EventType.DISCARD: ItemStatus.DISCARDED,
    EventType.RESTORE: ItemStatus.AVAILABLE,
}


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


async def sticky_availability(session: AsyncSession, item_id: uuid.UUID) -> ItemStatus:
    """The item's manually-/report-set availability, ignoring the loan state.

    Returns AVAILABLE when there is no availability event (or the latest is a Restore).
    """
    result = await session.execute(
        select(Event.event_type)
        .where(Event.item_id == item_id, Event.event_type.in_(_AVAILABILITY_EVENTS))
        .order_by(Event.created_at.desc(), Event.id.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None:
        return ItemStatus.AVAILABLE
    return _AVAILABILITY_STATUS[EventType(latest)]


def combine_status(
    sticky: ItemStatus, holder: uuid.UUID | None
) -> tuple[ItemStatus, uuid.UUID | None]:
    """Combine sticky availability with the loan holder by priority.

    Discarded > Lost > Checked out > Unavailable > Available.
    """
    if sticky == ItemStatus.DISCARDED:
        return ItemStatus.DISCARDED, None
    if sticky == ItemStatus.LOST:
        return ItemStatus.LOST, None
    if holder is not None:
        return ItemStatus.CHECKED_OUT, holder
    if sticky == ItemStatus.UNAVAILABLE:
        return ItemStatus.UNAVAILABLE, None
    return ItemStatus.AVAILABLE, None


async def item_status(session: AsyncSession, item: Item) -> tuple[ItemStatus, uuid.UUID | None]:
    """Compute (status, holder_user_id) for an item from its event log."""
    sticky = await sticky_availability(session, item.id)
    holder = None
    # Discarded/Lost items have left circulation; no need to look up a holder.
    if sticky not in (ItemStatus.DISCARDED, ItemStatus.LOST):
        holder = await latest_checkout_holder(session, item.id)
    return combine_status(sticky, holder)


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
