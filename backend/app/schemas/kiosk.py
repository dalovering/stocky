from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel

from app.schemas.inventory import ItemRead
from app.schemas.user import UserDetail


class ScanKind(StrEnum):
    USER = "user"
    ITEM = "item"
    UNKNOWN = "unknown"


class ScanRequest(BaseModel):
    barcode: str
    # The user currently logged in at the kiosk, if any (so an item scan can act on them).
    active_user_id: uuid.UUID | None = None


class ScanAction(StrEnum):
    """What the kiosk should do in response to a scan, for the passive-scan UX."""

    LOGIN = "login"  # a user card was scanned
    CHECKED_OUT = "checked_out"  # item auto-checked-out to the active user
    CHECKED_IN = "checked_in"  # item auto-checked-in from the active user
    OPEN_MODAL = "open_modal"  # ambiguous (held by another user, no active user, etc.)
    UNKNOWN = "unknown"  # barcode matched nothing


class ScanResponse(BaseModel):
    kind: ScanKind
    action: ScanAction
    message: str
    user: UserDetail | None = None
    item: ItemRead | None = None


class ItemActionRequest(BaseModel):
    item_id: uuid.UUID
    user_id: uuid.UUID | None = None
    note: str | None = None
