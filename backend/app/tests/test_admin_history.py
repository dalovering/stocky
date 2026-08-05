"""The admin history-log endpoint: filtering and pagination over the real API."""

from __future__ import annotations

import pytest


@pytest.fixture
async def history(admin_client):
    """A user and item with a checkout + checkin + damage report recorded."""
    user = (await admin_client.post("/api/admin/users", json={"name": "Ada"})).json()
    item_type = (await admin_client.post("/api/admin/item-types", json={"name": "Calc"})).json()
    item = (
        await admin_client.post(
            "/api/admin/items", json={"item_type_id": item_type["id"], "name": "Calc #1"}
        )
    ).json()
    await admin_client.post(
        "/api/kiosk/checkout", json={"item_id": item["id"], "user_id": user["id"]}
    )
    await admin_client.post(
        "/api/kiosk/checkin", json={"item_id": item["id"], "user_id": user["id"]}
    )
    await admin_client.post(
        "/api/kiosk/report-damage", json={"item_id": item["id"], "note": "screen cracked"}
    )
    return {"user": user, "item": item}


@pytest.mark.asyncio
async def test_events_returns_paginated_envelope(admin_client, history):
    page = (await admin_client.get("/api/admin/events")).json()
    assert set(page) == {"items", "total", "limit", "offset"}
    # create + checkout + checkin + damage_report = 4 events.
    assert page["total"] == 4
    # Newest first.
    assert page["items"][0]["event_type"] == "damage_report"
    # Joined names are present.
    assert page["items"][0]["item_name"] == "Calc #1"


@pytest.mark.asyncio
async def test_events_filter_by_type(admin_client, history):
    page = (await admin_client.get("/api/admin/events", params={"event_type": "checkout"})).json()
    assert page["total"] == 1
    assert page["items"][0]["event_type"] == "checkout"


@pytest.mark.asyncio
async def test_events_free_text_search_matches_note(admin_client, history):
    page = (await admin_client.get("/api/admin/events", params={"q": "cracked"})).json()
    assert page["total"] == 1
    assert page["items"][0]["note"] == "screen cracked"


@pytest.mark.asyncio
async def test_events_pagination(admin_client, history):
    first = (await admin_client.get("/api/admin/events", params={"limit": 2, "offset": 0})).json()
    second = (await admin_client.get("/api/admin/events", params={"limit": 2, "offset": 2})).json()
    assert first["total"] == 4
    assert len(first["items"]) == 2
    assert len(second["items"]) == 2
    ids = {e["id"] for e in first["items"]} | {e["id"] for e in second["items"]}
    assert len(ids) == 4  # no overlap across pages


@pytest.mark.asyncio
async def test_events_requires_admin(client):
    assert (await client.get("/api/admin/events")).status_code == 401
