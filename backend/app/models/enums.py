"""Shared enumerations for the domain model.

Condition (physical wear) and ItemStatus (availability) are deliberately separate concerns:
Condition is a stored attribute of the item; ItemStatus is *derived* from the event log (plus
the item's manually-set availability events). See `services/status.py`.

These enums are stored as plain VARCHAR (see the model `sa_type=String` columns), not native
Postgres ENUM types, so adding or removing a value is a Python-only change with no DB-type
migration. Validation happens at the Pydantic/schema layer.
"""

from __future__ import annotations

from enum import StrEnum


class Condition(StrEnum):
    """Physical condition of an item. Stored on the item; admin-editable.

    New items become Good the first time they're checked out; a damage report sets Damaged.
    """

    ON_ORDER = "On order"
    NEW = "New"
    GOOD = "Good"
    FAIR = "Fair"
    WORN = "Worn"
    DAMAGED = "Damaged"


class EventType(StrEnum):
    """Event-sourced history entries. Item status is derived from these."""

    CREATE = "create"
    CHECKOUT = "checkout"
    CHECKIN = "checkin"
    DAMAGE_REPORT = "damage_report"
    LOSS_REPORT = "loss_report"
    DISCARD = "discard"
    REPAIR = "repair"
    MARK_UNAVAILABLE = "mark_unavailable"  # admin marks an item unavailable
    RESTORE = "restore"  # admin resets an item back to available
    ATTENDANCE = "attendance"  # user-only (item_id is NULL): first kiosk scan of the day


class ItemStatus(StrEnum):
    """Derived, not stored — the current availability of an item.

    Checked out / Available come from the check-in/out log. Unavailable / Lost / Discarded are
    "sticky" states set by a damage/loss report or an explicit admin action, and cleared by an
    admin Restore.
    """

    CHECKED_OUT = "Checked out"
    AVAILABLE = "Available"
    UNAVAILABLE = "Unavailable"
    LOST = "Lost"
    DISCARDED = "Discarded"


class UserStatus(StrEnum):
    """Lifecycle state of a user. Stored on the user; admin-editable."""

    ACTIVE = "Active"
    INACTIVE = "Inactive"
