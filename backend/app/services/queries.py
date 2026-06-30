"""SQL query builders shared by more than one router.

Keeping these in one place means the public (`/api/inventory`) and admin (`/api/admin`) views
filter and list items identically — each router still applies its own auth and serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, distinct, func, or_, select

from app.models import Event, EventType, Item, User


def item_filter_query(
    q: str | None = None,
    type_id: uuid.UUID | None = None,
    location: str | None = None,
) -> Select:
    """Select items matching the optional name/type/location filters, ordered by name."""
    stmt = select(Item)
    if type_id is not None:
        stmt = stmt.where(Item.item_type_id == type_id)
    if location:
        stmt = stmt.where(Item.location == location)
    if q:
        stmt = stmt.where(Item.name.ilike(f"%{q}%"))
    return stmt.order_by(Item.name)


def event_filter_query(
    *,
    event_type: EventType | None = None,
    user_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    count: bool = False,
) -> Select:
    """Build the admin history query (or its COUNT) with the given filters.

    Joins items (for the name) and left-joins users (user_id is nullable for system events), so a
    single query carries the item/user names and a free-text `q` can match the note or either name.
    """
    if count:
        stmt = select(func.count(Event.id))
    else:
        stmt = select(Event, Item.name.label("item_name"), User.name.label("user_name"))
    stmt = stmt.join(Item, Event.item_id == Item.id).outerjoin(User, Event.user_id == User.id)

    if event_type is not None:
        stmt = stmt.where(Event.event_type == event_type)
    if user_id is not None:
        stmt = stmt.where(Event.user_id == user_id)
    if item_id is not None:
        stmt = stmt.where(Event.item_id == item_id)
    if date_from is not None:
        stmt = stmt.where(Event.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Event.created_at <= date_to)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Event.note.ilike(like), Item.name.ilike(like), User.name.ilike(like)))

    if not count:
        stmt = stmt.order_by(Event.created_at.desc(), Event.id.desc())
    return stmt


def distinct_locations_query() -> Select:
    """Distinct, non-null item locations ordered alphabetically (for location pickers)."""
    return select(distinct(Item.location)).where(Item.location.is_not(None)).order_by(Item.location)
