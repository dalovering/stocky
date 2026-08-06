"""Label-printer API tests over the real app and a real postgres:18 container.

No printer hardware exists in CI, and no fake printer object stands in for one — what is
tested here is everything up to the wire: real rows -> real serializers -> the exact
raster/TSPL bytes, plus auth and error mapping. The preview decode test reads the Code128
back out of the served PNG and compares it to the row's barcode column, end to end.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.tests.test_label_raster import _barcode_runs, _decode_code128


@pytest.fixture
async def fixtures(admin_client):
    group = (await admin_client.post("/api/admin/groups", json={"name": "Room 12"})).json()
    user = (
        await admin_client.post("/api/admin/users", json={"name": "Ada", "group_id": group["id"]})
    ).json()
    item_type = (
        await admin_client.post("/api/admin/item-types", json={"name": "Calculator"})
    ).json()
    item = (
        await admin_client.post(
            "/api/admin/items",
            json={"item_type_id": item_type["id"], "name": "Calc #1", "location": "Cabinet A"},
        )
    ).json()
    return {"group": group, "user": user, "item_type": item_type, "item": item}


MISSING_ID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.asyncio
async def test_previews_require_admin(client):
    for path in (
        f"/api/admin/print/items/{MISSING_ID}/preview.png",
        f"/api/admin/print/users/{MISSING_ID}/preview.png",
    ):
        assert (await client.get(path)).status_code == 401


@pytest.mark.asyncio
async def test_preview_404_for_unknown_ids(admin_client):
    assert (
        await admin_client.get(f"/api/admin/print/items/{MISSING_ID}/preview.png")
    ).status_code == 404
    assert (
        await admin_client.get(f"/api/admin/print/users/{MISSING_ID}/preview.png")
    ).status_code == 404


@pytest.mark.asyncio
async def test_item_preview_decodes_to_the_row_barcode(admin_client, fixtures):
    resp = await admin_client.get(f"/api/admin/print/items/{fixtures['item']['id']}/preview.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")

    image = Image.open(BytesIO(resp.content)).convert("1")
    # Default stock is 50x30 mm: 384 printable dots (48 mm head cap) x 240.
    assert image.size == (384, 240)
    assert _decode_code128(_barcode_runs(image)) == fixtures["item"]["barcode"]


@pytest.mark.asyncio
async def test_user_preview_decodes_to_the_row_barcode(admin_client, fixtures):
    resp = await admin_client.get(f"/api/admin/print/users/{fixtures['user']['id']}/preview.png")
    assert resp.status_code == 200
    image = Image.open(BytesIO(resp.content)).convert("1")
    assert _decode_code128(_barcode_runs(image)) == fixtures["user"]["barcode"]


@pytest.mark.asyncio
async def test_preview_respects_configured_label_size(admin_client, fixtures):
    await admin_client.patch(
        "/api/admin/settings", json={"label_width_mm": 40, "label_height_mm": 30}
    )
    resp = await admin_client.get(f"/api/admin/print/items/{fixtures['item']['id']}/preview.png")
    image = Image.open(BytesIO(resp.content)).convert("1")
    assert image.size == (320, 240)
    assert _decode_code128(_barcode_runs(image)) == fixtures["item"]["barcode"]


@pytest.mark.asyncio
async def test_preview_on_too_narrow_stock_409s_with_guidance(admin_client, fixtures):
    # A Stocky barcode needs 33 mm printable width; 30 mm stock can't carry it.
    await admin_client.patch(
        "/api/admin/settings", json={"label_width_mm": 30, "label_height_mm": 20}
    )
    resp = await admin_client.get(f"/api/admin/print/items/{fixtures['item']['id']}/preview.png")
    assert resp.status_code == 409
    assert "wider label stock" in resp.json()["detail"]
