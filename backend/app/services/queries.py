"""SQL query builders shared by more than one router.

Keeping these in one place means the public (`/api/inventory`) and admin (`/api/admin`) views
filter and list items identically — each router still applies its own auth and serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventType, Group, Item, ItemStatus, ItemType, User, UserStatus
from app.services.status import _AVAILABILITY_EVENTS, _LOAN_CLOSING

# Sentinel filter value meaning "items with no location" (NULL). Shared with the frontend, which
# sends it as a `location` query value alongside real location strings.
NO_LOCATION = "__none__"


async def group_names(session: AsyncSession) -> dict[uuid.UUID, str]:
    """id -> name for every group (for resolving group_id to a display name)."""
    return {g.id: g.name for g in (await session.execute(select(Group))).scalars()}


async def item_type_names(session: AsyncSession) -> dict[uuid.UUID, str]:
    """id -> name for every item type."""
    return {t.id: t.name for t in (await session.execute(select(ItemType))).scalars()}


# --- Bulk row fetches for the label-printing endpoints (name-ordered, like the PDF views) ---


async def items_by_ids(session: AsyncSession, ids: list[uuid.UUID]) -> list[Item]:
    if not ids:
        return []
    query = select(Item).where(Item.id.in_(ids)).order_by(Item.name)
    return list((await session.execute(query)).scalars().all())


async def items_by_type_ids(session: AsyncSession, type_ids: list[uuid.UUID]) -> list[Item]:
    if not type_ids:
        return []
    query = select(Item).where(Item.item_type_id.in_(type_ids)).order_by(Item.name)
    return list((await session.execute(query)).scalars().all())


async def users_by_ids(session: AsyncSession, ids: list[uuid.UUID]) -> list[User]:
    if not ids:
        return []
    query = select(User).where(User.id.in_(ids)).order_by(User.name)
    return list((await session.execute(query)).scalars().all())


async def users_by_group_ids(session: AsyncSession, group_ids: list[uuid.UUID]) -> list[User]:
    """Direct members only — same semantics as the group ID-cards PDF."""
    if not group_ids:
        return []
    query = select(User).where(User.group_id.in_(group_ids)).order_by(User.name)
    return list((await session.execute(query)).scalars().all())


def _latest_event_per_item(*event_types: EventType, columns: list):
    """A `DISTINCT ON (item_id)` subquery selecting the latest of the given event types per item.

    `created_at DESC, id DESC` makes "latest" deterministic (same ordering as
    `serialize_items_bulk`). `columns` are the extra `Event` columns to carry out.
    """
    return (
        select(Event.item_id, *columns)
        .where(Event.event_type.in_(event_types))
        .order_by(Event.item_id, Event.created_at.desc(), Event.id.desc())
        .distinct(Event.item_id)
        .subquery()
    )


def item_read_query(
    q: str | None = None,
    type_id: list[uuid.UUID] | None = None,
    location: list[str] | None = None,
    condition: list[str] | None = None,
    status: list[ItemStatus] | None = None,
    needs_review: bool | None = None,
) -> Select:
    """Select items with their derived status, filtered by the given criteria, ordered by name.

    This is the **SQL twin of `services/status.py`**: it computes each item's availability
    `status` (and current holder / checkout time) directly in Postgres so the list can be filtered
    and sorted by the *derived* status, not just stored columns. The status CASE mirrors
    `combine_status` + `_AVAILABILITY_STATUS` exactly (priority Discarded > Lost > Checked out >
    Unavailable > Available); `test_item_read_query.py` asserts the two agree. Each result row is
    `(Item, status, holder_user_id, checked_out_at)` — feed it to `serialize_read_rows`.
    """
    avail = _latest_event_per_item(*_AVAILABILITY_EVENTS, columns=[Event.event_type])
    loan = _latest_event_per_item(
        EventType.CHECKOUT,
        *_LOAN_CLOSING,
        columns=[Event.event_type, Event.user_id, Event.created_at],
    )

    status_expr = case(
        (avail.c.event_type == EventType.DISCARD, ItemStatus.DISCARDED),
        (avail.c.event_type == EventType.LOSS_REPORT, ItemStatus.LOST),
        (loan.c.event_type == EventType.CHECKOUT, ItemStatus.CHECKED_OUT),
        (
            avail.c.event_type.in_([EventType.DAMAGE_REPORT, EventType.MARK_UNAVAILABLE]),
            ItemStatus.UNAVAILABLE,
        ),
        else_=ItemStatus.AVAILABLE,
    )
    # Holder / checkout time only apply while the derived status is "Checked out".
    on_loan = status_expr == ItemStatus.CHECKED_OUT
    holder_expr = case((on_loan, loan.c.user_id))
    checked_out_at_expr = case((on_loan, loan.c.created_at))

    stmt = (
        select(
            Item,
            status_expr.label("status"),
            holder_expr.label("holder_user_id"),
            checked_out_at_expr.label("checked_out_at"),
        )
        .outerjoin(avail, avail.c.item_id == Item.id)
        .outerjoin(loan, loan.c.item_id == Item.id)
    )

    if type_id:
        stmt = stmt.where(Item.item_type_id.in_(type_id))
    if location:
        names = [loc for loc in location if loc != NO_LOCATION]
        clauses = []
        if names:
            clauses.append(Item.location.in_(names))
        if NO_LOCATION in location:
            clauses.append(Item.location.is_(None))
        if clauses:
            stmt = stmt.where(or_(*clauses))
    if condition:
        stmt = stmt.where(Item.condition.in_(condition))
    if status:
        stmt = stmt.where(status_expr.in_(status))
    if needs_review is not None:
        stmt = stmt.where(Item.needs_review.is_(needs_review))
    if q:
        like = f"%{q}%"
        stmt = stmt.join(ItemType, ItemType.id == Item.item_type_id).where(
            or_(
                Item.name.ilike(like),
                Item.barcode.ilike(like),
                Item.location.ilike(like),
                ItemType.name.ilike(like),
            )
        )
    return stmt.order_by(Item.name)


def user_filter_query(
    q: str | None = None,
    status: list[UserStatus] | None = None,
    group_id: uuid.UUID | None = None,
) -> Select:
    """Select users matching the optional name/barcode/group search + status filter, by name."""
    stmt = select(User)
    if group_id is not None:
        stmt = stmt.where(User.group_id == group_id)
    if status:
        stmt = stmt.where(User.status.in_(status))
    if q:
        like = f"%{q}%"
        stmt = stmt.outerjoin(Group, Group.id == User.group_id).where(
            or_(User.name.ilike(like), User.barcode.ilike(like), Group.name.ilike(like))
        )
    return stmt.order_by(User.name)


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

    Left-joins items AND users — both FKs are nullable (user_id for system events, item_id for
    user-only events like attendance) — so a single query carries the item/user names and a
    free-text `q` can match the note or either name without dropping null-side rows.
    """
    if count:
        stmt = select(func.count(Event.id))
    else:
        stmt = select(Event, Item.name.label("item_name"), User.name.label("user_name"))
    stmt = stmt.outerjoin(Item, Event.item_id == Item.id).outerjoin(User, Event.user_id == User.id)

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
