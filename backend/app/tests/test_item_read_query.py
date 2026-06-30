"""The SQL item read model (`item_read_query`) — filtering + agreement with `status.py`.

`item_read_query` computes each item's *derived* availability status in Postgres so the list can be
filtered/sorted by it. The critical test pins that SQL derivation to the canonical Python one in
`services/status.py` across a matrix of event histories; the rest exercise each filter. Runs against
the real postgres:18 container (the SQL CASE/DISTINCT ON only behaves correctly on the real DB).
"""

from __future__ import annotations

import pytest

from app.models import Condition, Item, ItemStatus, ItemType, User
from app.services import events as event_svc
from app.services.queries import NO_LOCATION, item_read_query
from app.services.status import item_status


async def _type(session, name="Calculator") -> ItemType:
    t = ItemType(name=name)
    session.add(t)
    await session.flush()
    return t


async def _item(
    session, type_id, name, barcode, *, location=None, condition=Condition.GOOD
) -> Item:
    item = Item(
        item_type_id=type_id, name=name, barcode=barcode, location=location, condition=condition
    )
    session.add(item)
    await session.flush()
    return item


async def _run(session, **kwargs):
    return (await session.execute(item_read_query(**kwargs))).all()


async def _names(session, **kwargs) -> set[str]:
    return {row[0].name for row in await _run(session, **kwargs)}


@pytest.mark.asyncio
async def test_read_query_status_matches_status_service(session):
    """The SQL-derived status/holder must equal services/status.py for every event history."""
    t = await _type(session)
    user = User(name="Ada", barcode="U0000000001")
    session.add(user)
    await session.flush()

    n = 0

    async def make(name) -> Item:
        nonlocal n
        n += 1
        return await _item(session, t.id, name, f"I{n:010d}", condition=Condition.NEW)

    items: list[Item] = []
    items.append(await make("fresh"))  # Available

    i = await make("out")  # Checked out
    await event_svc.check_out(session, i, user.id)
    items.append(i)

    i = await make("returned")  # Available
    await event_svc.check_out(session, i, user.id)
    await event_svc.check_in(session, i, user.id)
    items.append(i)

    i = await make("damaged-idle")  # Unavailable
    await event_svc.report_damage(session, i, None)
    items.append(i)

    i = await make("out-damaged")  # Checked out (loan beats Unavailable)
    await event_svc.check_out(session, i, user.id)
    await event_svc.report_damage(session, i, user.id)
    items.append(i)

    i = await make("returned-damaged")  # Unavailable (sticky surfaces on return)
    await event_svc.check_out(session, i, user.id)
    await event_svc.report_damage(session, i, user.id)
    await event_svc.check_in(session, i, user.id)
    items.append(i)

    i = await make("lost")  # Lost
    await event_svc.report_loss(session, i, None)
    items.append(i)

    i = await make("out-lost")  # Lost (no holder)
    await event_svc.check_out(session, i, user.id)
    await event_svc.report_loss(session, i, user.id)
    items.append(i)

    i = await make("discarded")  # Discarded
    await event_svc.discard(session, i)
    items.append(i)

    i = await make("unavailable")  # Unavailable
    await event_svc.mark_unavailable(session, i)
    items.append(i)

    i = await make("unavail-restored")  # Available
    await event_svc.mark_unavailable(session, i)
    await event_svc.restore(session, i)
    items.append(i)

    i = await make("discard-restored")  # Available
    await event_svc.discard(session, i)
    await event_svc.restore(session, i)
    items.append(i)

    await session.flush()

    rows = await _run(session)
    by_id = {row[0].id: row for row in rows}
    assert len(by_id) == len(items)
    for item in items:
        expected_status, expected_holder = await item_status(session, item)
        row = by_id[item.id]
        assert row.status == expected_status, f"{item.name}: status"
        assert row.holder_user_id == expected_holder, f"{item.name}: holder"
        assert (row.checked_out_at is not None) == (
            expected_status == ItemStatus.CHECKED_OUT
        ), f"{item.name}: checked_out_at"


@pytest.mark.asyncio
async def test_filter_by_status_single_and_multi(session):
    t = await _type(session)
    await _item(session, t.id, "avail", "I0000000001")
    lost = await _item(session, t.id, "lost", "I0000000002")
    await event_svc.mark_lost(session, lost)
    discarded = await _item(session, t.id, "discarded", "I0000000003")
    await event_svc.discard(session, discarded)
    await session.flush()

    assert await _names(session, status=[ItemStatus.AVAILABLE]) == {"avail"}
    assert await _names(session, status=[ItemStatus.LOST]) == {"lost"}
    assert await _names(session, status=[ItemStatus.LOST, ItemStatus.DISCARDED]) == {
        "lost",
        "discarded",
    }
    # No status filter returns all three.
    assert await _names(session) == {"avail", "lost", "discarded"}


@pytest.mark.asyncio
async def test_filter_by_condition(session):
    t = await _type(session)
    await _item(session, t.id, "good", "I0000000001", condition=Condition.GOOD)
    await _item(session, t.id, "worn", "I0000000002", condition=Condition.WORN)
    await _item(session, t.id, "damaged", "I0000000003", condition=Condition.DAMAGED)
    await session.flush()

    assert await _names(session, condition=[Condition.GOOD]) == {"good"}
    assert await _names(session, condition=[Condition.WORN, Condition.DAMAGED]) == {
        "worn",
        "damaged",
    }


@pytest.mark.asyncio
async def test_filter_by_location_including_no_location(session):
    t = await _type(session)
    await _item(session, t.id, "a", "I0000000001", location="Shelf 1")
    await _item(session, t.id, "b", "I0000000002", location="Shelf 2")
    await _item(session, t.id, "c", "I0000000003", location=None)
    await session.flush()

    assert await _names(session, location=["Shelf 1"]) == {"a"}
    assert await _names(session, location=[NO_LOCATION]) == {"c"}
    assert await _names(session, location=["Shelf 1", NO_LOCATION]) == {"a", "c"}


@pytest.mark.asyncio
async def test_filter_by_type(session):
    t1 = await _type(session, "Calculator")
    t2 = await _type(session, "Microscope")
    await _item(session, t1.id, "calc", "I0000000001")
    await _item(session, t2.id, "scope", "I0000000002")
    await session.flush()

    assert await _names(session, type_id=[t1.id]) == {"calc"}
    assert await _names(session, type_id=[t1.id, t2.id]) == {"calc", "scope"}


@pytest.mark.asyncio
async def test_filter_by_needs_review(session):
    t = await _type(session)
    flagged = await _item(session, t.id, "flagged", "I0000000001")
    await event_svc.report_damage(session, flagged, None)  # sets needs_review = True
    await _item(session, t.id, "clean", "I0000000002")
    await session.flush()

    assert await _names(session, needs_review=True) == {"flagged"}
    assert await _names(session, needs_review=False) == {"clean"}


@pytest.mark.asyncio
async def test_search_matches_name_barcode_location_and_type_name(session):
    t = await _type(session, "Graphing Calculator")
    await _item(session, t.id, "Widget", "I0000000042", location="Lab A")
    await _item(session, t.id, "Other", "I0000000099", location="Closet")
    await session.flush()

    assert await _names(session, q="widg") == {"Widget"}  # name
    assert await _names(session, q="0000042") == {"Widget"}  # barcode
    assert await _names(session, q="lab") == {"Widget"}  # location
    assert await _names(session, q="graphing") == {"Widget", "Other"}  # type name


@pytest.mark.asyncio
async def test_items_endpoint_multivalue_params_and_derived_status_filter(admin_client):
    """End-to-end: repeated query params parse, and the derived-status filter works over HTTP."""
    t = (await admin_client.post("/api/admin/item-types", json={"name": "Calc"})).json()
    a = (
        await admin_client.post(
            "/api/admin/items", json={"item_type_id": t["id"], "name": "A", "condition": "Good"}
        )
    ).json()
    b = (
        await admin_client.post(
            "/api/admin/items", json={"item_type_id": t["id"], "name": "B", "condition": "Worn"}
        )
    ).json()
    await admin_client.post(f"/api/admin/items/{b['id']}/status", json={"status": "Lost"})

    # Derived status filter.
    resp = await admin_client.get("/api/admin/items", params={"status": "Lost"})
    assert [i["name"] for i in resp.json()] == ["B"]
    assert resp.json()[0]["status"] == "Lost"

    # Repeated query keys (multi-select).
    resp = await admin_client.get(
        "/api/admin/items", params=[("condition", "Good"), ("condition", "Worn")]
    )
    assert {i["name"] for i in resp.json()} == {"A", "B"}

    # No filter returns both with derived status present.
    resp = await admin_client.get("/api/admin/items")
    assert {i["name"] for i in resp.json()} == {"A", "B"}
    assert a["status"] == "Available"


@pytest.mark.asyncio
async def test_item_stats_endpoint(admin_client):
    t = (await admin_client.post("/api/admin/item-types", json={"name": "Calc"})).json()
    it = (
        await admin_client.post("/api/admin/items", json={"item_type_id": t["id"], "name": "A"})
    ).json()
    await admin_client.post("/api/admin/items", json={"item_type_id": t["id"], "name": "B"})
    assert (await admin_client.get("/api/admin/items/stats")).json() == {
        "total": 2,
        "needs_review": 0,
    }
    await admin_client.patch(f"/api/admin/items/{it['id']}", json={"needs_review": True})
    assert (await admin_client.get("/api/admin/items/stats")).json() == {
        "total": 2,
        "needs_review": 1,
    }
