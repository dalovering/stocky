"""App settings + the kiosk inactive-user enforcement they gate."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_settings_default_and_update(admin_client):
    initial = (await admin_client.get("/api/admin/settings")).json()
    assert initial == {"kiosk_block_inactive_users": False}

    updated = (
        await admin_client.patch("/api/admin/settings", json={"kiosk_block_inactive_users": True})
    ).json()
    assert updated["kiosk_block_inactive_users"] is True

    # Persisted across reads.
    again = (await admin_client.get("/api/admin/settings")).json()
    assert again["kiosk_block_inactive_users"] is True


@pytest.mark.asyncio
async def test_settings_requires_admin(client):
    assert (await client.get("/api/admin/settings")).status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_blocked_only_when_enabled(admin_client):
    user = (
        await admin_client.post("/api/admin/users", json={"name": "Ada", "status": "Inactive"})
    ).json()

    # Setting off (default): an inactive user can still log in at the kiosk.
    scan = (await admin_client.post("/api/kiosk/scan", json={"barcode": user["barcode"]})).json()
    assert scan["action"] == "login"

    # Turn the setting on: now the same scan is blocked.
    await admin_client.patch("/api/admin/settings", json={"kiosk_block_inactive_users": True})
    scan = (await admin_client.post("/api/kiosk/scan", json={"barcode": user["barcode"]})).json()
    assert scan["action"] == "unknown"
    assert "inactive" in scan["message"].lower()
    assert scan["user"] is None


@pytest.mark.asyncio
async def test_inactive_user_blocked_from_checkout_when_enabled(admin_client):
    user = (
        await admin_client.post("/api/admin/users", json={"name": "Ada", "status": "Inactive"})
    ).json()
    item_type = (await admin_client.post("/api/admin/item-types", json={"name": "Calc"})).json()
    item = (
        await admin_client.post(
            "/api/admin/items", json={"item_type_id": item_type["id"], "name": "Calc #1"}
        )
    ).json()
    await admin_client.patch("/api/admin/settings", json={"kiosk_block_inactive_users": True})

    resp = await admin_client.post(
        "/api/kiosk/checkout", json={"item_id": item["id"], "user_id": user["id"]}
    )
    assert resp.status_code == 403
