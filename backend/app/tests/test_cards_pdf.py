"""Tag & ID-card PDF endpoints (SVG-template based) over the real API."""

from __future__ import annotations

import pytest


def _is_pdf(content: bytes) -> bool:
    return (
        content.startswith(b"%PDF-") and content.rstrip().endswith(b"%%EOF") and len(content) > 800
    )


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


@pytest.mark.asyncio
async def test_single_item_tag_pdf(admin_client, fixtures):
    resp = await admin_client.get(f"/api/admin/items/{fixtures['item']['id']}/tag.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert _is_pdf(resp.content)


@pytest.mark.asyncio
async def test_single_user_id_card_pdf(admin_client, fixtures):
    resp = await admin_client.get(f"/api/admin/users/{fixtures['user']['id']}/id-card.pdf")
    assert resp.status_code == 200
    assert _is_pdf(resp.content)


@pytest.mark.asyncio
async def test_item_type_tags_pdf(admin_client, fixtures):
    resp = await admin_client.get(f"/api/admin/item-types/{fixtures['item_type']['id']}/tags.pdf")
    assert _is_pdf(resp.content)


@pytest.mark.asyncio
async def test_group_id_cards_pdf(admin_client, fixtures):
    resp = await admin_client.get(f"/api/admin/groups/{fixtures['group']['id']}/id-cards.pdf")
    assert _is_pdf(resp.content)


@pytest.mark.asyncio
async def test_selection_tag_and_card_pdfs(admin_client, fixtures):
    tags = await admin_client.post(
        "/api/admin/items/tags.pdf", json={"ids": [fixtures["item"]["id"]]}
    )
    assert _is_pdf(tags.content)
    cards = await admin_client.post(
        "/api/admin/users/id-cards.pdf", json={"ids": [fixtures["user"]["id"]]}
    )
    assert _is_pdf(cards.content)


@pytest.mark.asyncio
async def test_tag_pdf_requires_admin(client):
    # require_admin runs before the handler, so any id 401s for an unauthenticated client.
    rid = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/api/admin/items/{rid}/tag.pdf")).status_code == 401


@pytest.mark.asyncio
async def test_single_item_tag_page_is_50x30_mm(admin_client, fixtures):
    """The single-tag page equals the label stock: 50x30mm = 141.73x85.04pt in the MediaBox."""
    resp = await admin_client.get(f"/api/admin/items/{fixtures['item']['id']}/tag.pdf")
    assert b"/MediaBox" in resp.content
    assert b"141.7" in resp.content
    assert b"85.0" in resp.content
