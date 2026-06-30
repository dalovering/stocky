"""Result of an xlsx import: per-action counts plus any per-row errors."""

from __future__ import annotations

from pydantic import BaseModel


class RowError(BaseModel):
    row: int  # 1-based row number in the sheet (row 1 is the header)
    message: str


class ImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    errors: list[RowError] = []
