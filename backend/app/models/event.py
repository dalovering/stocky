"""Event: the event-sourced history log. Item status & loans derive from these rows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.models.enums import EventType


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="items.id", index=True)
    # The user involved (e.g. who checked the item out). Null for admin/system events.
    user_id: uuid.UUID | None = Field(default=None, foreign_key="users.id", index=True)
    event_type: EventType = Field(index=True)
    note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
