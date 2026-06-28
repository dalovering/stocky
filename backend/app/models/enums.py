"""Shared enumerations for the domain model."""

from __future__ import annotations

from enum import StrEnum


class Condition(StrEnum):
    """Physical condition of an item (from the spec)."""

    NEW = "New"
    USED = "Used"
    LOST = "Lost"
    DAMAGED = "Damaged"
    DISCARDED = "Discarded"


class EventType(StrEnum):
    """Event-sourced history entries. Item status is derived from these."""

    CREATE = "create"
    CHECKOUT = "checkout"
    CHECKIN = "checkin"
    DAMAGE_REPORT = "damage_report"
    LOSS_REPORT = "loss_report"
    DISCARD = "discard"
    REPAIR = "repair"


class ItemStatus(StrEnum):
    """Derived, not stored — the current availability of an item."""

    AVAILABLE = "Available"
    ON_LOAN = "On loan"
    DAMAGED = "Damaged"
    LOST = "Lost"
    DISCARDED = "Discarded"
