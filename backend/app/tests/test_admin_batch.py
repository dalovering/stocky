"""Admin status changes and batch operations over the real API + database."""

from __future__ import annotations

import pytest


@pytest.fixture
async def inventory(admin_client):
    """A type with three items, plus a user; returns ids."""
    item_type = (
        await admin_client.post("/api/admin/item-types", json={"name": "Calculator"})
    ).json()
    other_type = (await admin_client.post("/api/admin/item-types", json={"name": "Book"})).json()
    items = [
        (
            await admin_client.post(
                "/api/admin/items",
                json={
                    "item_type_id": item_type["id"],
                    "name": f"Calc {n}",
                    "location": "Cabinet A",
                },
            )
        ).json()
        for n in range(3)
    ]
    user = (await admin_client.post("/api/admin/users", json={"name": "Ada"})).json()
    return {"type": item_type, "other_type": other_type, "items": items, "user": user}


@pytest.mark.asyncio
async def test_set_item_status_marks_unavailable_and_restores(admin_client, inventory):
    item = inventory["items"][0]
    out = (
        await admin_client.post(
            f"/api/admin/items/{item['id']}/status",
            json={"status": "Unavailable", "note": "missing battery cover"},
        )
    ).json()
    assert out["status"] == "Unavailable"

    restored = (
        await admin_client.post(
            f"/api/admin/items/{item['id']}/status", json={"status": "Available"}
        )
    ).json()
    assert restored["status"] == "Available"


@pytest.mark.asyncio
async def test_cannot_set_checked_out_status(admin_client, inventory):
    item = inventory["items"][0]
    resp = await admin_client.post(
        f"/api/admin/items/{item['id']}/status", json={"status": "Checked out"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_batch_set_item_status(admin_client, inventory):
    ids = [i["id"] for i in inventory["items"]]
    out = (
        await admin_client.post(
            "/api/admin/items/batch/status", json={"ids": ids, "status": "Discarded"}
        )
    ).json()
    assert {i["status"] for i in out} == {"Discarded"}


@pytest.mark.asyncio
async def test_batch_update_items_moves_type_and_location(admin_client, inventory):
    ids = [i["id"] for i in inventory["items"]]
    out = (
        await admin_client.patch(
            "/api/admin/items/batch",
            json={
                "ids": ids,
                "patch": {"item_type_id": inventory["other_type"]["id"], "location": "Shelf 9"},
            },
        )
    ).json()
    assert all(i["item_type_id"] == inventory["other_type"]["id"] for i in out)
    assert {i["location"] for i in out} == {"Shelf 9"}


@pytest.mark.asyncio
async def test_batch_clear_needs_review(admin_client, inventory):
    item = inventory["items"][0]
    # A damage report flags it for review.
    await admin_client.post("/api/kiosk/report-damage", json={"item_id": item["id"]})
    flagged = (await admin_client.get(f"/api/admin/items/{item['id']}")).json()
    assert flagged["needs_review"] is True

    out = (
        await admin_client.patch(
            "/api/admin/items/batch", json={"ids": [item["id"]], "patch": {"needs_review": False}}
        )
    ).json()
    assert out[0]["needs_review"] is False


@pytest.mark.asyncio
async def test_batch_delete_items(admin_client, inventory):
    ids = [i["id"] for i in inventory["items"]]
    resp = await admin_client.post("/api/admin/items/batch-delete", json={"ids": ids})
    assert resp.status_code == 204
    remaining = (await admin_client.get("/api/admin/items")).json()
    assert remaining == []


@pytest.mark.asyncio
async def test_batch_update_users_status_and_group(admin_client, inventory):
    group = (await admin_client.post("/api/admin/groups", json={"name": "Room 7"})).json()
    user = inventory["user"]
    out = (
        await admin_client.patch(
            "/api/admin/users/batch",
            json={"ids": [user["id"]], "patch": {"group_id": group["id"], "status": "Inactive"}},
        )
    ).json()
    assert out[0]["group_id"] == group["id"]
    assert out[0]["status"] == "Inactive"


@pytest.mark.asyncio
async def test_batch_delete_users_keeps_history(admin_client, inventory):
    user, item = inventory["user"], inventory["items"][0]
    await admin_client.post(
        "/api/kiosk/checkout", json={"item_id": item["id"], "user_id": user["id"]}
    )

    resp = await admin_client.post("/api/admin/users/batch-delete", json={"ids": [user["id"]]})
    assert resp.status_code == 204
    # The user is gone but the checkout event remains (now with no user).
    events = (await admin_client.get(f"/api/admin/items/{item['id']}/events")).json()
    assert any(e["event_type"] == "checkout" for e in events)
