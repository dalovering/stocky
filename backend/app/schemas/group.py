from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None
    permissions: dict = Field(default_factory=dict)
    semester_start: date | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    parent_id: uuid.UUID | None = None
    permissions: dict | None = None
    # PATCH semantics via exclude_unset: omitted = unchanged, explicit null = cleared.
    semester_start: date | None = None


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    permissions: dict
    semester_start: date | None = None


class GroupTree(GroupRead):
    """A group with its nested children and member count, for the admin tree view."""

    children: list[GroupTree] = Field(default_factory=list)
    user_count: int = 0
