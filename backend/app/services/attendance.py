"""The attendance report: scheduled days and per-user Present/Absent, computed server-side.

Rules (from the spec discussion in issue #2):
- A day is "scheduled" for a group when ANY of its direct members has attendance that day —
  groups are scored independently; child groups render nested but never roll up into parents.
- For every scheduled day, each direct member is Present (checked in that day) or Absent.
- Windows: today / this week (Monday-based) / since the group's semester_start. A group with no
  semester_start has no semester window — the report returns zero days and the UI explains.

Day bucketing happens in Postgres (`created_at AT TIME ZONE <timezone setting>` cast to DATE),
matching how the kiosk records attendance in the first place.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventType, Group, User
from app.schemas.attendance import AttendanceGroup, AttendanceReport, AttendanceUserRow, Timeframe
from app.services import settings as settings_svc


async def attendance_report(session: AsyncSession, timeframe: Timeframe) -> AttendanceReport:
    tz_name = await settings_svc.app_timezone(session)
    today = datetime.now(ZoneInfo(tz_name)).date()

    groups = list((await session.execute(select(Group))).scalars())
    users = list((await session.execute(select(User).order_by(User.name))).scalars())

    # One aggregate query: every (user, local day) attendance pair. Classroom scale keeps this
    # tiny (one row per user per day); windows are applied per group below.
    day = sa.cast(func.timezone(tz_name, Event.created_at), sa.Date).label("day")
    pairs = (
        await session.execute(
            select(Event.user_id, day)
            .where(Event.event_type == EventType.ATTENDANCE, Event.user_id.is_not(None))
            .group_by(Event.user_id, day)
        )
    ).all()
    days_by_user: dict[uuid.UUID, set[date]] = defaultdict(set)
    for user_id, attended in pairs:
        days_by_user[user_id].add(attended)

    members_by_group: dict[uuid.UUID | None, list[User]] = defaultdict(list)
    for user in users:
        members_by_group[user.group_id].append(user)

    def window_start(group: Group | None) -> date | None:
        if timeframe == "today":
            return today
        if timeframe == "week":
            return today - timedelta(days=today.weekday())  # Monday of the current week
        return group.semester_start if group is not None else None

    def build(group: Group | None, group_id: uuid.UUID | None, name: str) -> AttendanceGroup:
        members = members_by_group.get(group_id, [])
        start = window_start(group)
        if start is None:  # semester view without a semester_start: no window
            days: list[date] = []
        else:
            days = sorted(
                {
                    attended
                    for member in members
                    for attended in days_by_user.get(member.id, ())
                    if start <= attended <= today
                }
            )
        day_set = set(days)
        rows = [
            AttendanceUserRow(
                user_id=member.id,
                name=member.name,
                barcode=member.barcode,
                present=(present := sorted(days_by_user.get(member.id, set()) & day_set)),
                present_count=len(present),
                absent_count=len(days) - len(present),
            )
            for member in members
        ]
        return AttendanceGroup(
            group_id=group_id,
            group_name=name,
            semester_start=group.semester_start if group else None,
            days=days,
            users=rows,
            children=[
                build(child, child.id, child.name)
                for child in sorted(children_of[group_id], key=lambda g: g.name)
            ]
            if group_id is not None
            else [],
        )

    children_of: dict[uuid.UUID | None, list[Group]] = defaultdict(list)
    for group in groups:
        children_of[group.parent_id].append(group)

    roots = [
        build(group, group.id, group.name)
        for group in sorted(children_of[None], key=lambda g: g.name)
    ]
    if members_by_group.get(None):
        roots.append(build(None, None, "No group"))

    return AttendanceReport(timeframe=timeframe, timezone=tz_name, groups=roots)
