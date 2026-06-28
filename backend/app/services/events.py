"""Kiosk loan operations: checkout / checkin / report damage / report loss.

These functions enforce the business rules from the spec and append to the event log.
They raise `LoanError` for rule violations; the API layer maps that to HTTP 409.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Condition, Event, EventType, Item
from app.services.status import latest_checkout_holder


class LoanError(Exception):
    """A loan operation that violates the business rules (e.g. double checkout)."""


async def check_out(session: AsyncSession, item: Item, user_id: uuid.UUID) -> Event:
    holder = await latest_checkout_holder(session, item.id)
    if holder == user_id:
        raise LoanError("You already have this item checked out.")
    if holder is not None:
        raise LoanError("This item is currently checked out by another user.")
    if item.condition in (Condition.LOST, Condition.DISCARDED):
        raise LoanError(f"This item cannot be checked out (condition: {item.condition}).")
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
    item.condition = Condition.DAMAGED
    session.add(item)
    event = Event(item_id=item.id, user_id=user_id, event_type=EventType.DAMAGE_REPORT, note=note)
    session.add(event)
    return event


async def report_loss(
    session: AsyncSession, item: Item, user_id: uuid.UUID | None, note: str | None = None
) -> Event:
    """Mark an item lost. This also closes any open loan (it leaves circulation)."""
    item.condition = Condition.LOST
    session.add(item)
    event = Event(item_id=item.id, user_id=user_id, event_type=EventType.LOSS_REPORT, note=note)
    session.add(event)
    return event
