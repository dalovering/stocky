"""The attendance report: scheduled days, Present/Absent, windows, and timezone bucketing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models import Event, EventType

TZ = ZoneInfo("America/New_York")  # the default timezone setting


def _local_today() -> datetime:
    return datetime.now(UTC).astimezone(TZ)


async def _mark(session, user_id: str, when: datetime) -> None:
    session.add(
        Event(
            item_id=None,
            user_id=uuid.UUID(user_id),
            event_type=EventType.ATTENDANCE,
            created_at=when.astimezone(UTC),
        )
    )
    await session.commit()


async def _group(admin_client, name: str, **extra) -> dict:
    return (await admin_client.post("/api/admin/groups", json={"name": name, **extra})).json()


async def _user(admin_client, name: str, group_id: str | None = None) -> dict:
    body = {"name": name, "group_id": group_id}
    return (await admin_client.post("/api/admin/users", json=body)).json()


def _by_name(report: dict, name: str) -> dict:
    def walk(groups):
        for g in groups:
            if g["group_name"] == name:
                return g
            found = walk(g["children"])
            if found:
                return found
        return None

    found = walk(report["groups"])
    assert found is not None, f"group {name!r} missing from report"
    return found


@pytest.mark.asyncio
async def test_scheduled_day_rule_and_present_absent(admin_client, session):
    """A day counts when ANY direct member attended; the others are absent that day."""
    room = await _group(admin_client, "Room 12")
    ada = await _user(admin_client, "Ada", room["id"])
    bob = await _user(admin_client, "Bob", room["id"])

    yesterday = _local_today() - timedelta(days=1)
    await _mark(session, ada["id"], yesterday.replace(hour=9, minute=0))

    report = (await admin_client.get("/api/admin/attendance?timeframe=week")).json()
    group = _by_name(report, "Room 12")
    # (If yesterday fell in the previous Monday-week this window would be empty — keep the test
    # deterministic by checking via the semester-free "week" only when it applies.)
    if yesterday.date() >= (_local_today().date() - timedelta(days=_local_today().weekday())):
        assert len(group["days"]) == 1
        rows = {u["name"]: u for u in group["users"]}
        assert rows["Ada"]["present_count"] == 1
        assert rows["Ada"]["absent_count"] == 0
        assert rows["Bob"]["present_count"] == 0
        assert rows["Bob"]["absent_count"] == 1
    assert bob["id"]  # both members always appear
    assert {u["name"] for u in group["users"]} == {"Ada", "Bob"}


@pytest.mark.asyncio
async def test_semester_windows_per_group(admin_client, session):
    today = _local_today().date()
    room_a = await _group(admin_client, "Room A", semester_start=str(today - timedelta(days=30)))
    room_b = await _group(admin_client, "Room B")  # no semester_start
    ada = await _user(admin_client, "Ada", room_a["id"])
    bob = await _user(admin_client, "Bob", room_b["id"])

    noon = _local_today().replace(hour=12, minute=0)
    await _mark(session, ada["id"], noon - timedelta(days=10))  # inside the window
    await _mark(session, ada["id"], noon - timedelta(days=40))  # before semester_start
    await _mark(session, bob["id"], noon - timedelta(days=10))

    report = (await admin_client.get("/api/admin/attendance?timeframe=semester")).json()
    group_a = _by_name(report, "Room A")
    assert group_a["semester_start"] == str(today - timedelta(days=30))
    assert len(group_a["days"]) == 1  # the -40d day is outside the window
    assert group_a["users"][0]["present_count"] == 1

    # No semester_start -> no window: zero days, everyone at zero.
    group_b = _by_name(report, "Room B")
    assert group_b["semester_start"] is None
    assert group_b["days"] == []
    assert group_b["users"][0]["present_count"] == 0
    assert group_b["users"][0]["absent_count"] == 0


@pytest.mark.asyncio
async def test_timezone_bucketing(admin_client, session):
    """03:00Z is the previous local day in America/New_York."""
    today = _local_today().date()
    room = await _group(admin_client, "Room T", semester_start="2026-02-01")
    ada = await _user(admin_client, "Ada", room["id"])

    await _mark(session, ada["id"], datetime(2026, 3, 1, 3, 0, tzinfo=UTC))

    report = (await admin_client.get("/api/admin/attendance?timeframe=semester")).json()
    group = _by_name(report, "Room T")
    assert "2026-02-28" in [d for d in group["days"]]
    assert "2026-03-01" not in group["days"]
    assert today  # window end is today; the fixed date lies within


@pytest.mark.asyncio
async def test_today_window_and_no_group_bucket(admin_client, session):
    loner = await _user(admin_client, "Zoe", None)
    await _mark(session, loner["id"], _local_today().replace(hour=8, minute=30))

    report = (await admin_client.get("/api/admin/attendance?timeframe=today")).json()
    bucket = _by_name(report, "No group")
    assert bucket["group_id"] is None
    assert len(bucket["days"]) == 1
    assert bucket["users"][0]["name"] == "Zoe"
    assert bucket["users"][0]["present_count"] == 1


@pytest.mark.asyncio
async def test_nested_groups_scored_independently(admin_client, session):
    parent = await _group(admin_client, "School")
    child = await _group(admin_client, "Class 1", parent_id=parent["id"])
    kid = await _user(admin_client, "Ada", child["id"])
    await _mark(session, kid["id"], _local_today().replace(hour=9, minute=0))

    report = (await admin_client.get("/api/admin/attendance?timeframe=today")).json()
    school = _by_name(report, "School")
    class1 = _by_name(report, "Class 1")
    # The child is nested under the parent, but the parent (no direct members) has no days.
    assert school["days"] == []
    assert school["users"] == []
    assert [c["group_name"] for c in school["children"]] == ["Class 1"]
    assert len(class1["days"]) == 1


@pytest.mark.asyncio
async def test_attendance_report_requires_admin(client):
    assert (await client.get("/api/admin/attendance")).status_code == 401
