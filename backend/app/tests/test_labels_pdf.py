from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_labels_pdf_requires_admin(client):
    # The endpoint is admin-guarded like the rest of /api/admin.
    resp = await client.get("/api/admin/labels.pdf")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_labels_pdf_renders_users_and_inventory(admin_client):
    # A user (with a group) and an item (with a type) so both sections have content.
    group = (await admin_client.post("/api/admin/groups", json={"name": "Room 1"})).json()
    await admin_client.post("/api/admin/users", json={"name": "Ada", "group_id": group["id"]})
    item_type = (
        await admin_client.post("/api/admin/item-types", json={"name": "Calculator"})
    ).json()
    await admin_client.post(
        "/api/admin/items", json={"item_type_id": item_type["id"], "name": "Calc #1"}
    )

    resp = await admin_client.get("/api/admin/labels.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    body = resp.content
    # A valid, non-trivial PDF document.
    assert body.startswith(b"%PDF-")
    assert body.rstrip().endswith(b"%%EOF")
    assert len(body) > 1000


@pytest.mark.asyncio
async def test_labels_pdf_empty_database_still_valid(admin_client):
    # With no users or items, the endpoint still returns a valid PDF (empty-section notes).
    resp = await admin_client.get("/api/admin/labels.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF-")
