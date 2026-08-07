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
async def test_printer_info_requires_admin(client):
    assert (await client.get("/api/admin/printer")).status_code == 401


@pytest.mark.asyncio
async def test_printer_info_unconfigured_no_device_io(admin_client):
    info = (await admin_client.get("/api/admin/printer")).json()
    assert info["configured"] is False
    assert info["enabled"] is False
    assert info["state"] == "Not configured"
    assert info["device"] is None
    assert info["label_width_mm"] == 50.0
    assert info["max_batch"] == 50
    # probe=true on an unconfigured printer is still a no-op, not an error
    probed = (await admin_client.get("/api/admin/printer?probe=true")).json()
    assert probed["state"] == "Not configured"


@pytest.mark.asyncio
async def test_printer_probe_unreachable_device(admin_client, monkeypatch):
    from app.core.config import settings as app_config

    monkeypatch.setattr(app_config, "printer_device", "/nonexistent/printer0")
    info = (await admin_client.get("/api/admin/printer")).json()
    assert info["configured"] is True
    assert info["state"] == "Not checked"  # no probe requested -> no device I/O
    probed = (await admin_client.get("/api/admin/printer?probe=true")).json()
    assert probed["state"] == "Unreachable"
    assert "/nonexistent/printer0" in probed["message"]


@pytest.mark.asyncio
async def test_preview_on_too_narrow_stock_409s_with_guidance(admin_client, fixtures):
    # A Stocky barcode needs 33 mm printable width; 30 mm stock can't carry it.
    await admin_client.patch(
        "/api/admin/settings", json={"label_width_mm": 30, "label_height_mm": 20}
    )
    resp = await admin_client.get(f"/api/admin/print/items/{fixtures['item']['id']}/preview.png")
    assert resp.status_code == 409
    assert "wider label stock" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Print endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_print_endpoints_require_admin(client):
    for path in (
        "/api/admin/print/items",
        "/api/admin/print/item-types",
        "/api/admin/print/users",
        "/api/admin/print/groups",
        "/api/admin/printer/test-print",
        "/api/admin/print/items/job.tspl",
        "/api/admin/print/users/job.tspl",
    ):
        assert (await client.post(path, json={"ids": []})).status_code == 401, path


@pytest.mark.asyncio
async def test_print_gates_disabled_then_unconfigured(admin_client, fixtures):
    ids = {"ids": [fixtures["item"]["id"]]}
    # printer_enabled defaults to False.
    resp = await admin_client.post("/api/admin/print/items", json=ids)
    assert resp.status_code == 409
    assert "turned off in Settings" in resp.json()["detail"]

    await admin_client.patch("/api/admin/settings", json={"printer_enabled": True})
    resp = await admin_client.post("/api/admin/print/items", json=ids)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "The label printer is not configured."


@pytest.mark.asyncio
async def test_test_print_bypasses_enabled_but_needs_device(admin_client):
    resp = await admin_client.post("/api/admin/printer/test-print")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "The label printer is not configured."


@pytest.mark.asyncio
async def test_print_unreachable_device_503s(admin_client, fixtures, monkeypatch):
    from app.core.config import settings as app_config

    monkeypatch.setattr(app_config, "printer_device", "/nonexistent/printer0")
    await admin_client.patch("/api/admin/settings", json={"printer_enabled": True})
    resp = await admin_client.post("/api/admin/print/items", json={"ids": [fixtures["item"]["id"]]})
    assert resp.status_code == 503
    assert "Could not open the printer device" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_print_end_to_end_through_a_pty(admin_client, fixtures, monkeypatch):
    """API -> real DB rows -> raster -> TSPL -> pty wire, with a CRC-valid status frame."""
    from app.core.config import settings as app_config
    from app.services import tspl
    from app.tests.test_printer_job import PtyResponder, _frame

    responder = PtyResponder([_frame(0, width_mm=50)])
    try:
        monkeypatch.setattr(app_config, "printer_device", responder.path)
        monkeypatch.setattr(app_config, "printer_transport", "serial")
        await admin_client.patch("/api/admin/settings", json={"printer_enabled": True})

        resp = await admin_client.post(
            "/api/admin/print/items", json={"ids": [fixtures["item"]["id"]]}
        )
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["printed"] == 1 and result["requested"] == 1
        assert result["warnings"] == []

        responder.wait_for(result["bytes_sent"])
        wire = bytes(responder.received)
        assert wire.startswith(tspl.STATUS_QUERY + b"SIZE 50.0 mm,30.0 mm\r\n")
        assert wire.count(b"PRINT 1\r\n") == 1

        # The badge path too, against the same device.
        resp = await admin_client.post(
            "/api/admin/print/users", json={"ids": [fixtures["user"]["id"]]}
        )
        assert resp.status_code == 200 and resp.json()["printed"] == 1
    finally:
        responder.close()


@pytest.mark.asyncio
async def test_print_group_and_type_expansion(admin_client, fixtures, monkeypatch):
    from app.core.config import settings as app_config
    from app.tests.test_printer_job import PtyResponder, _frame

    # A second user in the group and a second item of the type.
    await admin_client.post(
        "/api/admin/users", json={"name": "Grace", "group_id": fixtures["group"]["id"]}
    )
    await admin_client.post(
        "/api/admin/items",
        json={"item_type_id": fixtures["item_type"]["id"], "name": "Calc #2"},
    )

    responder = PtyResponder([_frame(0, width_mm=50)])
    try:
        monkeypatch.setattr(app_config, "printer_device", responder.path)
        monkeypatch.setattr(app_config, "printer_transport", "serial")
        await admin_client.patch("/api/admin/settings", json={"printer_enabled": True})

        resp = await admin_client.post(
            "/api/admin/print/groups", json={"ids": [fixtures["group"]["id"]]}
        )
        assert resp.json()["printed"] == 2  # Ada + Grace

        resp = await admin_client.post(
            "/api/admin/print/item-types", json={"ids": [fixtures["item_type"]["id"]]}
        )
        assert resp.json()["printed"] == 2  # Calc #1 + Calc #2
    finally:
        responder.close()


@pytest.mark.asyncio
async def test_print_empty_selection_is_a_clean_zero(admin_client, monkeypatch):
    from app.core.config import settings as app_config

    monkeypatch.setattr(app_config, "printer_device", "/dev/null")
    await admin_client.patch("/api/admin/settings", json={"printer_enabled": True})
    resp = await admin_client.post("/api/admin/print/items", json={"ids": []})
    assert resp.status_code == 200
    assert resp.json() == {"printed": 0, "requested": 0, "bytes_sent": 0, "warnings": []}


@pytest.mark.asyncio
async def test_tspl_job_export_needs_no_device_or_enable(admin_client, fixtures):
    from app.services import tspl

    resp = await admin_client.post(
        "/api/admin/print/items/job.tspl", json={"ids": [fixtures["item"]["id"]]}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    job = resp.content
    assert job.startswith(tspl.STATUS_QUERY + b"SIZE 50.0 mm,30.0 mm\r\n")
    assert job.count(b"PRINT 1\r\n") == 1
    # One 50x30 label: 48 bytes x 240 rows of bitmap inside the job.
    assert b"BITMAP 0,0,48,240," in job
    assert len(job) > 48 * 240

    badge = await admin_client.post(
        "/api/admin/print/users/job.tspl", json={"ids": [fixtures["user"]["id"]]}
    )
    assert badge.status_code == 200
    assert badge.content.count(b"PRINT 1\r\n") == 1
