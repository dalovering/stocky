from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_group_and_user_crud(admin_client):
    # Create a parent group and a nested child.
    parent = (await admin_client.post("/api/admin/groups", json={"name": "School"})).json()
    child = (
        await admin_client.post(
            "/api/admin/groups", json={"name": "Room 1", "parent_id": parent["id"]}
        )
    ).json()

    tree = (await admin_client.get("/api/admin/groups/tree")).json()
    assert len(tree) == 1
    assert tree[0]["name"] == "School"
    assert tree[0]["children"][0]["name"] == "Room 1"

    # Create a user; barcode is auto-generated.
    user = (
        await admin_client.post("/api/admin/users", json={"name": "Ada", "group_id": child["id"]})
    ).json()
    assert user["barcode"]
    assert user["group_name"] == "Room 1"

    # Regenerate the barcode -> it changes.
    old_barcode = user["barcode"]
    regened = (await admin_client.post(f"/api/admin/users/{user['id']}/barcode")).json()
    assert regened["barcode"] != old_barcode


@pytest.mark.asyncio
async def test_item_type_and_item_crud(admin_client):
    item_type = (
        await admin_client.post(
            "/api/admin/item-types",
            json={"name": "Calculator", "manufacturer": "TI"},
        )
    ).json()

    item = (
        await admin_client.post(
            "/api/admin/items",
            json={
                "item_type_id": item_type["id"],
                "name": "Calc #1",
                "location": "Cabinet A",
                "description": None,
            },
        )
    ).json()
    assert item["barcode"]
    assert item["status"] == "Available"
    # Item description falls back to nothing here; type name is enriched.
    assert item["item_type_name"] == "Calculator"

    # Creation event recorded in history.
    events = (await admin_client.get(f"/api/admin/items/{item['id']}/events")).json()
    assert any(e["event_type"] == "create" for e in events)

    # Distinct-location lookup reflects the new item.
    locations = (await admin_client.get("/api/admin/locations")).json()
    assert "Cabinet A" in locations

    # Cannot delete a type that still has items.
    resp = await admin_client.delete(f"/api/admin/item-types/{item_type['id']}")
    assert resp.status_code == 409
