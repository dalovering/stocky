from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    name: str
    parent_id: uuid.UUID | None = None
    permissions: dict = Field(default_factory=dict)


class GroupUpdate(BaseModel):
    name: str | None = None
    parent_id: uuid.UUID | None = None
    permissions: dict | None = None


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    permissions: dict


class GroupTree(GroupRead):
    """A group with its nested children and member count, for the admin tree view."""

    children: list[GroupTree] = Field(default_factory=list)
    user_count: int = 0
