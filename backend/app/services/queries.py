"""SQL query builders shared by more than one router.

Keeping these in one place means the public (`/api/inventory`) and admin (`/api/admin`) views
filter and list items identically — each router still applies its own auth and serialization.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, distinct, select

from app.models import Item


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


def distinct_locations_query() -> Select:
    """Distinct, non-null item locations ordered alphabetically (for location pickers)."""
    return select(distinct(Item.location)).where(Item.location.is_not(None)).order_by(Item.location)
