"""Read models for restore-from-backup: the diff plan shown before anything is applied."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

# Detail lists are capped so a big database can't produce a megabyte response; the
# *_count fields are always the full numbers — never trust len(list) for totals.
DETAIL_CAP = 100


class SheetError(BaseModel):
    """A row (or sheet-level) problem that makes the backup unusable as uploaded."""

    sheet: str
    row: int | None = None  # None = a sheet-level problem (missing sheet, bad headers)
    message: str


class FieldChange(BaseModel):
    field: str
    old: str | None
    new: str | None


class RowChange(BaseModel):
    id: uuid.UUID
    label: str  # human handle: "name (barcode)" where available
    fields: list[FieldChange] = []  # populated for updates; empty for create/delete


class EntityPlan(BaseModel):
    """What restore would do to one table. Lists capped at DETAIL_CAP, counts exact."""

    kind: str  # "groups" | "item_types" | "users" | "items"
    creates: list[RowChange] = []
    updates: list[RowChange] = []
    deletes: list[RowChange] = []
    create_count: int = 0
    update_count: int = 0
    delete_count: int = 0
    unchanged: int = 0
    truncated: bool = False


class SettingChange(BaseModel):
    key: str
    old: str
    new: str


class RestorePlan(BaseModel):
    """The full diff between the uploaded backup and the live database.

    `errors` non-empty means the file can't be restored as-is and the rest of the plan is
    empty; apply refuses. `applied` is True only on the response that actually executed.
    """

    errors: list[SheetError] = []
    entities: list[EntityPlan] = []
    settings: list[SettingChange] = []
    # History is append-only, so its diff is additions and removals by event id.
    events_add: int = 0
    events_remove: int = 0
    events_relink: int = 0  # kept events whose item/user link or fields get corrected
    events_unchanged: int = 0
    applied: bool = False
