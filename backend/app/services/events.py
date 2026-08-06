"""Loan & availability operations: checkout / checkin / damage / loss / admin status changes.

These functions enforce the business rules from the spec and append to the event log. They
raise `LoanError` for rule violations; the API layer maps that to HTTP 409. Availability
changes are recorded as events so the derived `ItemStatus` (see `services/status.py`) stays the
single source of truth — nothing here stores a status directly.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Condition, Event, EventType, Item, ItemStatus
from app.services.status import item_status, latest_checkout_holder


class LoanError(Exception):
    """A loan operation that violates the business rules (e.g. double checkout)."""


async def check_out(session: AsyncSession, item: Item, user_id: uuid.UUID) -> Event:
    holder = await latest_checkout_holder(session, item.id)
    if holder == user_id:
        raise LoanError("You already have this item checked out.")
    if holder is not None:
        raise LoanError("This item is currently checked out by another user.")
    status, _ = await item_status(session, item)
    if status in (ItemStatus.LOST, ItemStatus.DISCARDED, ItemStatus.UNAVAILABLE):
        raise LoanError(f"This item cannot be checked out (status: {status}).")
    # A brand-new item becomes "Good" the moment it's first issued.
    if item.condition == Condition.NEW:
        item.condition = Condition.GOOD
        session.add(item)
    event = Event(item_id=item.id, user_id=user_id, event_type=EventType.CHECKOUT)
    session.add(event)
    return event


async def check_in(session: AsyncSession, item: Item, user_id: uuid.UUID) -> Event:
    holder = await latest_checkout_holder(session, item.id)
    if holder is None:
        raise LoanError("This item is not currently checked out.")
    if holder != user_id:
        raise LoanError("This item is checked out by another user.")
    event = Event(item_id=item.id, user_id=user_id, event_type=EventType.CHECKIN)
    session.add(event)
    return event


async def report_damage(
    session: AsyncSession, item: Item, user_id: uuid.UUID | None, note: str | None = None
) -> Event:
    """Record damage: set the physical condition, flag for review, and append the event."""
    item.condition = Condition.DAMAGED
    item.needs_review = True
    session.add(item)
    event = Event(item_id=item.id, user_id=user_id, event_type=EventType.DAMAGE_REPORT, note=note)
    session.add(event)
    return event


async def report_loss(
    session: AsyncSession, item: Item, user_id: uuid.UUID | None, note: str | None = None
) -> Event:
    """Mark an item lost. This also closes any open loan (it leaves circulation)."""
    item.needs_review = True
    session.add(item)
    event = Event(item_id=item.id, user_id=user_id, event_type=EventType.LOSS_REPORT, note=note)
    session.add(event)
    return event


async def detach_user_history(session: AsyncSession, user_ids: Sequence[uuid.UUID]) -> None:
    """Prepare user deletion: drop user-only events, anonymize the rest.

    Attendance events belong to the user alone (item_id is NULL) — after the user is gone they
    would be fully-orphaned rows, so they are deleted. Item history is kept with user_id nulled,
    exactly as before.
    """
    if not user_ids:
        return
    await session.execute(
        sa.delete(Event).where(
            Event.user_id.in_(user_ids), Event.event_type == EventType.ATTENDANCE
        )
    )
    await session.execute(sa.update(Event).where(Event.user_id.in_(user_ids)).values(user_id=None))


async def record_attendance(session: AsyncSession, user_id: uuid.UUID, tz: str) -> Event | None:
    """Append an attendance event if this is the user's first ID scan of the local day.

    "Day" is the calendar day in the app's configured time zone, computed in Postgres
    (`created_at AT TIME ZONE tz` cast to date) so the boundary matches the attendance report.
    Returns None when today's attendance is already recorded. Two near-simultaneous scans could
    in principle both pass the check — a unique index can't guard this because the timezone cast
    isn't immutable — but a single kiosk makes that window irrelevant in practice.
    """

    def local_day(column: object) -> sa.Cast:
        return sa.cast(func.timezone(tz, column), sa.Date)

    existing = await session.scalar(
        select(Event.id)
        .where(
            Event.user_id == user_id,
            Event.event_type == EventType.ATTENDANCE,
            local_day(Event.created_at) == local_day(func.now()),
        )
        .limit(1)
    )
    if existing is not None:
        return None
    event = Event(item_id=None, user_id=user_id, event_type=EventType.ATTENDANCE)
    session.add(event)
    return event


# ---------------------------------------------------------------------------
# Admin availability changes — each appends the matching availability event.
# ---------------------------------------------------------------------------
def _availability_event(
    item: Item, event_type: EventType, user_id: uuid.UUID | None, note: str | None
) -> Event:
    event = Event(item_id=item.id, user_id=user_id, event_type=event_type, note=note)
    return event


async def mark_unavailable(
    session: AsyncSession, item: Item, note: str | None = None, user_id: uuid.UUID | None = None
) -> Event:
    event = _availability_event(item, EventType.MARK_UNAVAILABLE, user_id, note)
    session.add(event)
    return event


async def mark_lost(
    session: AsyncSession, item: Item, note: str | None = None, user_id: uuid.UUID | None = None
) -> Event:
    event = _availability_event(item, EventType.LOSS_REPORT, user_id, note)
    session.add(event)
    return event


async def discard(
    session: AsyncSession, item: Item, note: str | None = None, user_id: uuid.UUID | None = None
) -> Event:
    event = _availability_event(item, EventType.DISCARD, user_id, note)
    session.add(event)
    return event


async def restore(
    session: AsyncSession,
    item: Item,
    note: str | None = None,
    user_id: uuid.UUID | None = None,
    clear_review: bool = True,
) -> Event:
    """Reset an item back to Available and (by default) clear its needs-review flag."""
    if clear_review:
        item.needs_review = False
        session.add(item)
    event = _availability_event(item, EventType.RESTORE, user_id, note)
    session.add(event)
    return event
