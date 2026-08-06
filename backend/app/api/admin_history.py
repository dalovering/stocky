"""Admin: the event history log — a filterable, paginated view of every event."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.api.responses import xlsx_response
from app.core.db import get_session
from app.models import EventType
from app.models.common import utcnow
from app.schemas.common import Page
from app.schemas.inventory import EventRead
from app.services import spreadsheet
from app.services.queries import event_filter_query

router = APIRouter(
    prefix="/api/admin", tags=["admin:history"], dependencies=[Depends(require_admin)]
)

# Default window when the caller doesn't constrain by date or subject: the last three months.
_DEFAULT_WINDOW = timedelta(days=90)


@router.get("/events.xlsx")
async def export_events(
    event_type: EventType | None = None,
    user_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """History as a spreadsheet: everything matching the filters.

    Deliberately no pagination and no 90-day default — an export means "give me all of it",
    scoped only by whatever filters the caller passes (user_id/item_id/dates/type/q).
    """
    content = await spreadsheet.events_workbook(
        session,
        event_type=event_type,
        user_id=user_id,
        item_id=item_id,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )
    return xlsx_response(content, "stocky-history.xlsx")


@router.get("/events", response_model=Page[EventRead])
async def list_events(
    event_type: EventType | None = None,
    user_id: uuid.UUID | None = None,
    item_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> Page[EventRead]:
    """Most-recent-first event history. Defaults to the last three months unless narrowed."""
    # Only default the window for the broad view; an explicit item/user filter shows full history.
    if date_from is None and item_id is None and user_id is None:
        date_from = utcnow() - _DEFAULT_WINDOW

    filters = dict(
        event_type=event_type,
        user_id=user_id,
        item_id=item_id,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )
    total = await session.scalar(event_filter_query(count=True, **filters))
    rows = (await session.execute(event_filter_query(**filters).limit(limit).offset(offset))).all()
    items = [
        EventRead(
            id=event.id,
            item_id=event.item_id,
            item_name=item_name,
            user_id=event.user_id,
            user_name=user_name,
            event_type=event.event_type,
            note=event.note,
            created_at=event.created_at,
        )
        for event, item_name, user_name in rows
    ]
    return Page(items=items, total=int(total or 0), limit=limit, offset=offset)
