"""App settings + the kiosk inactive-user enforcement they gate."""

from __future__ import annotations

import pytest

# The complete settings document with its defaults. Deliberately exact: adding a settings key
# must be a conscious choice here too, since the document is served verbatim to the admin UI.
DEFAULTS = {
    "kiosk_block_inactive_users": False,
    "kiosk_idle_timeout_seconds": 60,
    "admin_idle_timeout_minutes": 15,
    "timezone": "America/New_York",
}


@pytest.mark.asyncio
async def test_settings_default_and_update(admin_client):
    initial = (await admin_client.get("/api/admin/settings")).json()
    assert initial == DEFAULTS

    updated = (
        await admin_client.patch("/api/admin/settings", json={"kiosk_block_inactive_users": True})
    ).json()
    assert updated["kiosk_block_inactive_users"] is True

    # Persisted across reads.
    again = (await admin_client.get("/api/admin/settings")).json()
    assert again["kiosk_block_inactive_users"] is True


@pytest.mark.asyncio
async def test_settings_timeouts_and_timezone_roundtrip(admin_client):
    updated = (
        await admin_client.patch(
            "/api/admin/settings",
            json={
                "kiosk_idle_timeout_seconds": 120,
                "admin_idle_timeout_minutes": 0,
                "timezone": "America/Chicago",
            },
        )
    ).json()
    assert updated["kiosk_idle_timeout_seconds"] == 120
    assert updated["admin_idle_timeout_minutes"] == 0
    assert updated["timezone"] == "America/Chicago"

    again = (await admin_client.get("/api/admin/settings")).json()
    assert again == {**DEFAULTS, **updated}


@pytest.mark.asyncio
async def test_settings_rejects_bad_values(admin_client):
    for bad_patch in (
        {"timezone": "Not/AZone"},
        {"kiosk_idle_timeout_seconds": -1},
        {"kiosk_idle_timeout_seconds": 3601},
        {"admin_idle_timeout_minutes": 481},
    ):
        resp = await admin_client.patch("/api/admin/settings", json=bad_patch)
        assert resp.status_code == 422, bad_patch


@pytest.mark.asyncio
async def test_settings_requires_admin(client):
    assert (await client.get("/api/admin/settings")).status_code == 401


@pytest.mark.asyncio
async def test_kiosk_config_public_and_minimal(client):
    # Unauthenticated read works (the kiosk has no admin session, and none exists yet here)…
    config = (await client.get("/api/kiosk/config")).json()
    # …and exposes exactly the kiosk-safe keys, nothing more (leak guard).
    assert config == {"idle_timeout_seconds": 60}

    # Reflects admin changes.
    from app.tests.conftest import TEST_ADMIN_PASSWORD

    await client.post("/api/auth/setup", json={"password": TEST_ADMIN_PASSWORD})
    await client.patch("/api/admin/settings", json={"kiosk_idle_timeout_seconds": 300})
    config = (await client.get("/api/kiosk/config")).json()
    assert config == {"idle_timeout_seconds": 300}


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
