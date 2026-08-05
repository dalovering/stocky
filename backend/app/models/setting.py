"""Setting: a single app-level configuration value, keyed by name.

A tiny key/value store (value is JSON, so a setting can be a bool, number, string, or object).
Typed access and defaults live in `services/settings.py`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Setting(SQLModel, table=True):
    __tablename__ = "settings"

    key: str = Field(primary_key=True)
    value: Any = Field(default=None, sa_column=Column(JSON, nullable=False))
