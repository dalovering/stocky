"""Seed demo data so the kiosk and views are usable immediately.

Idempotent-ish: it refuses to run if data already exists (unless STOCKY_SEED_FORCE=1),
so you don't accidentally duplicate demo rows. Run with `make seed`.

The data is deliberately varied — 8 users across 3 rooms (one Inactive), 20 items of 5 types in a
range of conditions, and events that produce every item status (Checked out, Available,
Unavailable, Lost, Discarded) — so the admin filters and history have something to show.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.core.db import async_session_maker
from app.models import Condition, Event, EventType, Group, Item, ItemType, User, UserStatus
from app.services import barcode as barcode_svc
from app.services import events as event_svc


async def _seed() -> None:
    async with async_session_maker() as session:
        existing = await session.scalar(select(func.count()).select_from(User))
        if existing and os.getenv("STOCKY_SEED_FORCE") != "1":
            print(
                f"Database already has {existing} users; skipping seed "
                "(set STOCKY_SEED_FORCE=1 to override)."
            )
            return

        # Groups (nested): School > Room 12 / Room 14 / Room 16
        school = Group(name="Lincoln Elementary", permissions={"manage": True})
        session.add(school)
        await session.flush()
        room12 = Group(name="Room 12", parent_id=school.id)
        room14 = Group(name="Room 14", parent_id=school.id)
        room16 = Group(name="Room 16", parent_id=school.id)
        session.add_all([room12, room14, room16])
        await session.flush()

        # Users — 8 across the rooms; Dennis is Inactive (to exercise the user-status filter).
        def user(name: str, group: Group, status: UserStatus = UserStatus.ACTIVE) -> User:
            return User(
                name=name,
                group_id=group.id,
                status=status,
                barcode=barcode_svc.generate_user_code(),
            )

        users = [
            user("Ada Lovelace", room12),
            user("Alan Turing", room12),
            user("Barbara Liskov", room12),
            user("Grace Hopper", room14),
            user("Katherine Johnson", room14),
            user("Dennis Ritchie", room14, status=UserStatus.INACTIVE),
            user("Linus Torvalds", room16),
            user("Margaret Hamilton", room16),
        ]
        session.add_all(users)

        # Item types (5)
        calc = ItemType(
            name="TI-84 Graphing Calculator",
            manufacturer="Texas Instruments",
            description="Graphing calculator for math class.",
            cost=Decimal("120.00"),
            upc_isbn="033317200030",
        )
        novel = ItemType(
            name="To Kill a Mockingbird",
            manufacturer="Harper Perennial",
            author="Harper Lee",
            publish_date=date(1960, 7, 11),
            description="Classroom reading copy.",
            cost=Decimal("9.99"),
            upc_isbn="9780060935467",
        )
        chromebook = ItemType(
            name="Chromebook",
            manufacturer="Acer",
            description="11-inch student laptop.",
            cost=Decimal("249.00"),
        )
        microscope = ItemType(
            name="Compound Microscope",
            manufacturer="AmScope",
            description="40x–1000x student microscope.",
            cost=Decimal("85.00"),
        )
        paint = ItemType(
            name="Acrylic Paint Set",
            manufacturer="Crayola",
            description="24-color acrylic paint set.",
            cost=Decimal("18.50"),
        )
        session.add_all([calc, novel, chromebook, microscope, paint])
        await session.flush()

        # Items (20) — (type, name, location, condition), in a spread of conditions.
        C = Condition
        specs = [
            (calc, "Calculator #1", "Cabinet A", C.GOOD),
            (calc, "Calculator #2", "Cabinet A", C.GOOD),
            (calc, "Calculator #3", "Cabinet A", C.FAIR),
            (calc, "Calculator #4", "Cabinet A", C.NEW),
            (calc, "Calculator #5", "Cabinet A", C.WORN),
            (calc, "Calculator #6", "Cabinet A", C.NEW),
            (novel, "Mockingbird Copy 1", "Shelf 3", C.GOOD),
            (novel, "Mockingbird Copy 2", "Shelf 3", C.FAIR),
            (novel, "Mockingbird Copy 3", "Shelf 3", C.WORN),
            (novel, "Mockingbird Copy 4", "Shelf 3", C.GOOD),
            (novel, "Mockingbird Copy 5", "Shelf 3", C.NEW),
            (chromebook, "Chromebook #1", "Cart 1", C.GOOD),
            (chromebook, "Chromebook #2", "Cart 1", C.GOOD),
            (chromebook, "Chromebook #3", "Cart 1", C.FAIR),
            (chromebook, "Chromebook #4", "Cart 1", C.ON_ORDER),
            (microscope, "Microscope #1", "Lab Bench", C.GOOD),
            (microscope, "Microscope #2", "Lab Bench", C.FAIR),
            (microscope, "Microscope #3", "Lab Bench", C.ON_ORDER),
            (paint, "Paint Set #1", "Art Closet", C.NEW),
            (paint, "Paint Set #2", "Art Closet", C.WORN),
        ]
        items = [
            Item(
                item_type_id=t.id,
                name=name,
                location=loc,
                condition=cond,
                barcode=barcode_svc.generate_item_code(),
            )
            for t, name, loc, cond in specs
        ]
        session.add_all(items)
        await session.flush()
        for item in items:
            session.add(Event(item_id=item.id, event_type=EventType.CREATE))
        await session.flush()

        # Events that produce a spread of statuses (via the real loan/availability services).
        by_name = {item.name: item for item in items}
        # Open loans -> Checked out
        await event_svc.check_out(session, by_name["Calculator #1"], users[0].id)
        await event_svc.check_out(session, by_name["Mockingbird Copy 1"], users[3].id)
        # Returned (leaves history) -> Available
        await event_svc.check_out(session, by_name["Chromebook #1"], users[4].id)
        await event_svc.check_in(session, by_name["Chromebook #1"], users[4].id)
        # Damage -> Unavailable + needs review
        await event_svc.report_damage(
            session, by_name["Microscope #1"], users[6].id, note="cracked eyepiece"
        )
        # Loss -> Lost + needs review
        await event_svc.report_loss(
            session, by_name["Calculator #5"], users[1].id, note="left on the bus"
        )
        # Discard -> Discarded
        await event_svc.discard(session, by_name["Paint Set #2"], note="dried out, beyond use")

        await session.commit()

        print(f"Seed complete: {len(users)} users, {len(items)} items across 5 types.")
        print("Sample barcodes (use these at the kiosk):")
        for u in users[:3]:
            print(f"  USER  {u.name:<18} {u.barcode}")
        for item in items[:3]:
            print(f"  ITEM  {item.name:<20} {item.barcode}")


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
