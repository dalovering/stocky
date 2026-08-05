"""Shared response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class Page[T](BaseModel):
    """One page of a larger result set: the rows plus the total for pagination controls."""

    items: list[T]
    total: int
    limit: int
    offset: int
