"""Seed demo data so the kiosk and views are usable immediately.

Idempotent-ish: it refuses to run if data already exists (unless STOCKY_SEED_FORCE=1),
so you don't accidentally duplicate demo rows. Run with `make seed`.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.core.db import async_session_maker
from app.models import Condition, Event, EventType, Group, Item, ItemType, User
from app.services import barcode as barcode_svc


async def _seed() -> None:
    async with async_session_maker() as session:
        existing = await session.scalar(select(func.count()).select_from(User))
        if existing and os.getenv("STOCKY_SEED_FORCE") != "1":
            print(
                f"Database already has {existing} users; skipping seed "
                "(set STOCKY_SEED_FORCE=1 to override)."
            )
            return

        # Groups (nested): School > Room 12 ; School > Room 14
        school = Group(name="Lincoln Elementary", permissions={"manage": True})
        session.add(school)
        await session.flush()
        room12 = Group(name="Room 12", parent_id=school.id)
        room14 = Group(name="Room 14", parent_id=school.id)
        session.add_all([room12, room14])
        await session.flush()

        # Users
        students = [
            User(name="Ada Lovelace", group_id=room12.id, barcode=barcode_svc.generate_user_code()),
            User(name="Alan Turing", group_id=room12.id, barcode=barcode_svc.generate_user_code()),
            User(name="Grace Hopper", group_id=room14.id, barcode=barcode_svc.generate_user_code()),
        ]
        session.add_all(students)

        # Item types
        calculator = ItemType(
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
        session.add_all([calculator, novel])
        await session.flush()

        # Items
        items = [
            Item(
                item_type_id=calculator.id,
                name="Calculator #1",
                location="Cabinet A",
                condition=Condition.NEW,
                barcode=barcode_svc.generate_item_code(),
            ),
            Item(
                item_type_id=calculator.id,
                name="Calculator #2",
                location="Cabinet A",
                condition=Condition.GOOD,
                barcode=barcode_svc.generate_item_code(),
            ),
            Item(
                item_type_id=novel.id,
                name="Mockingbird Copy 1",
                location="Shelf 3",
                condition=Condition.FAIR,
                barcode=barcode_svc.generate_item_code(),
            ),
            Item(
                item_type_id=novel.id,
                name="Mockingbird Copy 2",
                location="Shelf 3",
                condition=Condition.NEW,
                barcode=barcode_svc.generate_item_code(),
            ),
        ]
        session.add_all(items)
        await session.flush()
        for item in items:
            session.add(Event(item_id=item.id, event_type=EventType.CREATE))

        # One active loan so the kiosk has something to show.
        session.add(
            Event(item_id=items[0].id, user_id=students[0].id, event_type=EventType.CHECKOUT)
        )

        await session.commit()

        print("Seed complete.")
        print("Sample barcodes (use these at the kiosk):")
        for s in students:
            print(f"  USER  {s.name:<16} {s.barcode}")
        for item in items:
            print(f"  ITEM  {item.name:<20} {item.barcode}")


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
