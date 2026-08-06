"""Read models for the attendance report (admin Attendance tab)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Timeframe = Literal["today", "week", "semester"]


class AttendanceUserRow(BaseModel):
    user_id: uuid.UUID
    name: str
    barcode: str
    # The subset of the group's scheduled days this user checked in on, ascending.
    present: list[date]
    present_count: int
    absent_count: int


class AttendanceGroup(BaseModel):
    group_id: uuid.UUID | None  # None = the "No group" bucket
    group_name: str
    semester_start: date | None
    # Scheduled days, ascending: days in the window when ANY direct member has attendance.
    days: list[date]
    users: list[AttendanceUserRow]
    children: list[AttendanceGroup] = Field(default_factory=list)


class AttendanceReport(BaseModel):
    timeframe: Timeframe
    timezone: str
    groups: list[AttendanceGroup]
