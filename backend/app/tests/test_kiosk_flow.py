from __future__ import annotations

import pytest


@pytest.fixture
async def fixtures(admin_client):
    """Create a user and an item; return their ids and barcodes."""
    user = (await admin_client.post("/api/admin/users", json={"name": "Ada"})).json()
    item_type = (
        await admin_client.post("/api/admin/item-types", json={"name": "Calculator"})
    ).json()
    item = (
        await admin_client.post(
            "/api/admin/items", json={"item_type_id": item_type["id"], "name": "Calc #1"}
        )
    ).json()
    return {"user": user, "item": item}


@pytest.mark.asyncio
async def test_scan_user_logs_in(admin_client, fixtures):
    user = fixtures["user"]
    resp = await admin_client.post("/api/kiosk/scan", json={"barcode": user["barcode"]})
    body = resp.json()
    assert body["kind"] == "user"
    assert body["action"] == "login"
    assert body["user"]["id"] == user["id"]


@pytest.mark.asyncio
async def test_passive_checkout_then_checkin(admin_client, fixtures):
    user, item = fixtures["user"], fixtures["item"]

    # First scan of the item (with active user) -> checkout.
    out = (
        await admin_client.post(
            "/api/kiosk/scan",
            json={"barcode": item["barcode"], "active_user_id": user["id"]},
        )
    ).json()
    assert out["action"] == "checked_out"
    assert out["item"]["status"] == "On loan"
    assert out["item"]["holder_user_id"] == user["id"]

    # User now shows one current loan.
    detail = (await admin_client.get(f"/api/kiosk/user/{user['id']}")).json()
    assert detail["loan_count"] == 1

    # Second scan -> checkin.
    back = (
        await admin_client.post(
            "/api/kiosk/scan",
            json={"barcode": item["barcode"], "active_user_id": user["id"]},
        )
    ).json()
    assert back["action"] == "checked_in"
    assert back["item"]["status"] == "Available"


@pytest.mark.asyncio
async def test_cannot_double_checkout(admin_client, fixtures):
    user, item = fixtures["user"], fixtures["item"]
    await admin_client.post(
        "/api/kiosk/checkout", json={"item_id": item["id"], "user_id": user["id"]}
    )
    # Explicit second checkout is rejected.
    resp = await admin_client.post(
        "/api/kiosk/checkout", json={"item_id": item["id"], "user_id": user["id"]}
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_item_held_by_other_opens_modal(admin_client, fixtures):
    item = fixtures["item"]
    user_a = fixtures["user"]
    user_b = (await admin_client.post("/api/admin/users", json={"name": "Alan"})).json()

    # A checks it out.
    await admin_client.post(
        "/api/kiosk/checkout", json={"item_id": item["id"], "user_id": user_a["id"]}
    )
    # B scans it while logged in -> ambiguous, open modal (no state change).
    resp = (
        await admin_client.post(
            "/api/kiosk/scan",
            json={"barcode": item["barcode"], "active_user_id": user_b["id"]},
        )
    ).json()
    assert resp["action"] == "open_modal"
    assert resp["item"]["holder_user_id"] == user_a["id"]


@pytest.mark.asyncio
async def test_report_loss_sets_status(admin_client, fixtures):
    item = fixtures["item"]
    resp = (
        await admin_client.post("/api/kiosk/report-loss", json={"item_id": item["id"]})
    ).json()
    assert resp["status"] == "Lost"
    assert resp["condition"] == "Lost"


@pytest.mark.asyncio
async def test_unknown_barcode(admin_client):
    resp = (await admin_client.post("/api/kiosk/scan", json={"barcode": "ZZZZ"})).json()
    assert resp["action"] == "unknown"
