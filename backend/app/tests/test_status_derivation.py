"""Derived ItemStatus truth table, exercised against the real database.

Status is computed from the event log (plus admin availability events), never stored. These
tests pin the priority rules: Discarded > Lost > Checked out > Unavailable > Available, and the
"sticky" nature of availability (a check-in does not clear a damaged item's Unavailable status).
"""

from __future__ import annotations

import pytest

from app.models import Condition, Item, ItemType, User
from app.services import events as event_svc
from app.services.serialize import serialize_item
from app.services.status import item_status


async def _make_item(session, condition=Condition.NEW) -> Item:
    item_type = ItemType(name="Calculator")
    session.add(item_type)
    await session.flush()
    item = Item(item_type_id=item_type.id, name="Calc", condition=condition, barcode="I0000000001")
    session.add(item)
    await session.flush()
    return item


async def _make_user(session, name="Ada", barcode="U0000000001") -> User:
    user = User(name=name, barcode=barcode)
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_new_item_is_available(session):
    item = await _make_item(session)
    status, holder = await item_status(session, item)
    assert status == "Available"
    assert holder is None


@pytest.mark.asyncio
async def test_checkout_makes_checked_out_and_new_becomes_good(session):
    item = await _make_item(session, condition=Condition.NEW)
    user = await _make_user(session)
    await event_svc.check_out(session, item, user.id)
    await session.flush()
    status, holder = await item_status(session, item)
    assert status == "Checked out"
    assert holder == user.id
    # A brand-new item becomes Good the first time it's issued.
    assert item.condition == Condition.GOOD


@pytest.mark.asyncio
async def test_checkin_returns_to_available(session):
    item = await _make_item(session)
    user = await _make_user(session)
    await event_svc.check_out(session, item, user.id)
    await session.flush()
    await event_svc.check_in(session, item, user.id)
    await session.flush()
    status, _ = await item_status(session, item)
    assert status == "Available"


@pytest.mark.asyncio
async def test_damage_makes_unavailable_and_sticks_through_checkin(session):
    item = await _make_item(session)
    user = await _make_user(session)
    await event_svc.check_out(session, item, user.id)
    await session.flush()
    # Damaged while on loan: still Checked out (loan wins over Unavailable).
    await event_svc.report_damage(session, item, user.id, note="cracked")
    await session.flush()
    status, _ = await item_status(session, item)
    assert status == "Checked out"
    assert item.needs_review is True
    # Returned: the sticky Unavailable now surfaces.
    await event_svc.check_in(session, item, user.id)
    await session.flush()
    status, _ = await item_status(session, item)
    assert status == "Unavailable"


@pytest.mark.asyncio
async def test_restore_clears_unavailable(session):
    item = await _make_item(session)
    await event_svc.report_damage(session, item, None)
    await session.flush()
    assert (await item_status(session, item))[0] == "Unavailable"
    await event_svc.restore(session, item)
    await session.flush()
    status, _ = await item_status(session, item)
    assert status == "Available"
    assert item.needs_review is False


@pytest.mark.asyncio
async def test_loss_is_terminal_over_checkout(session):
    item = await _make_item(session)
    user = await _make_user(session)
    await event_svc.check_out(session, item, user.id)
    await session.flush()
    await event_svc.report_loss(session, item, user.id)
    await session.flush()
    status, holder = await item_status(session, item)
    assert status == "Lost"
    assert holder is None


@pytest.mark.asyncio
async def test_discard_then_restore(session):
    item = await _make_item(session)
    await event_svc.discard(session, item)
    await session.flush()
    assert (await item_status(session, item))[0] == "Discarded"
    await event_svc.restore(session, item)
    await session.flush()
    assert (await item_status(session, item))[0] == "Available"


@pytest.mark.asyncio
async def test_cannot_checkout_unavailable_item(session):
    item = await _make_item(session)
    user = await _make_user(session)
    await event_svc.mark_unavailable(session, item)
    await session.flush()
    with pytest.raises(event_svc.LoanError):
        await event_svc.check_out(session, item, user.id)


@pytest.mark.asyncio
async def test_serialize_reports_needs_review_and_status(session):
    item = await _make_item(session)
    await event_svc.report_damage(session, item, None)
    await session.flush()
    view = await serialize_item(session, item)
    assert view.status == "Unavailable"
    assert view.needs_review is True
    assert view.condition == "Damaged"
