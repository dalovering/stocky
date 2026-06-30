from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import UserStatus
from app.schemas.inventory import ItemRead


class UserCreate(BaseModel):
    name: str
    group_id: uuid.UUID | None = None
    status: UserStatus = UserStatus.ACTIVE
    # Optional explicit barcode (e.g. registering an existing card); generated if omitted.
    barcode: str | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    group_id: uuid.UUID | None = None
    status: UserStatus | None = None
    barcode: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    group_id: uuid.UUID | None
    group_name: str | None = None
    status: UserStatus = UserStatus.ACTIVE
    barcode: str
    loan_count: int = 0


class UserDetail(UserRead):
    """Full user record including dynamic current loans (event history via its own endpoint)."""

    current_loans: list[ItemRead] = []


class UserBatchPatch(BaseModel):
    """Fields that can be applied to many users at once (omit a field to leave it unchanged)."""

    group_id: uuid.UUID | None = None
    status: UserStatus | None = None


class UserBatchUpdate(BaseModel):
    ids: list[uuid.UUID]
    patch: UserBatchPatch
