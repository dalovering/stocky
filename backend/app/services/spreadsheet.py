"""XLSX export/import of users and items.

Each sheet leads with an `action` column (C/U/D/blank) so an admin can round-trip the data
through Excel: download, edit, set actions, and re-upload. Import is best-effort — every row is
attempted and a per-row error never aborts the others; the response summarizes what happened.

openpyxl is pure-Python (Pi-friendly); we stream with write_only/read_only to keep memory low.
"""

from __future__ import annotations

import uuid
from io import BytesIO

from openpyxl import Workbook, load_workbook
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Condition, Event, EventType, Group, Item, ItemType, User, UserStatus
from app.schemas.imports import ImportResult, RowError
from app.services import barcode as barcode_svc

USER_HEADERS = ["action", "id", "barcode", "name", "group", "status"]
ITEM_HEADERS = [
    "action",
    "id",
    "barcode",
    "name",
    "item_type",
    "location",
    "condition",
    "needs_review",
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _workbook_bytes(headers: list[str], rows: list[list]) -> bytes:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _read_rows(content: bytes) -> list[tuple[int, dict]]:
    """Yield (row_number, {header: value}) for each data row, header-keyed and lower-cased."""
    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    raw_headers = next(rows, None) or []
    headers = [str(h).strip().lower() if h is not None else "" for h in raw_headers]
    out: list[tuple[int, dict]] = []
    for number, raw in enumerate(rows, start=2):  # row 1 is the header
        record = {headers[i]: raw[i] for i in range(len(headers)) if i < len(raw)}
        out.append((number, record))
    wb.close()
    return out


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _parse_uuid(value: object, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value).strip())
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid {field}: {value!r}.") from exc


def _parse_enum[E](enum_cls: type[E], value: object, field: str) -> E:
    text = _text(value)
    try:
        return enum_cls(text)
    except ValueError as exc:
        allowed = ", ".join(e.value for e in enum_cls)  # type: ignore[attr-defined]
        raise ValueError(f"Invalid {field} {text!r} (allowed: {allowed}).") from exc


async def _gen_unique_barcode(session: AsyncSession, model: type, prefix: str) -> str:
    for _ in range(10):
        code = barcode_svc.generate_code(prefix)
        if (
            await session.execute(select(model).where(model.barcode == code))
        ).scalar_one_or_none() is None:
            return code
    raise ValueError("Could not allocate a unique barcode.")


async def _resolve_barcode(
    session: AsyncSession,
    model: type,
    prefix: str,
    proposed: str | None,
    current: str | None = None,
) -> str:
    if proposed:
        if proposed == current:
            return proposed
        taken = (
            await session.execute(select(model).where(model.barcode == proposed))
        ).scalar_one_or_none()
        if taken is not None:
            raise ValueError(f"Barcode {proposed!r} already in use.")
        return proposed
    return current or await _gen_unique_barcode(session, model, prefix)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
async def users_workbook(session: AsyncSession) -> bytes:
    groups = {g.id: g.name for g in (await session.execute(select(Group))).scalars()}
    users = (await session.execute(select(User).order_by(User.name))).scalars()
    rows = [
        ["", str(u.id), u.barcode, u.name, groups.get(u.group_id, ""), str(u.status)] for u in users
    ]
    return _workbook_bytes(USER_HEADERS, rows)


async def import_users(session: AsyncSession, content: bytes) -> ImportResult:
    result = ImportResult()
    groups_by_name = {g.name: g for g in (await session.execute(select(Group))).scalars()}

    async def find(rec: dict) -> User | None:
        if _text(rec.get("id")):
            return await session.get(User, _parse_uuid(rec["id"], "id"))
        code = _text(rec.get("barcode"))
        if code:
            return (
                await session.execute(select(User).where(User.barcode == code))
            ).scalar_one_or_none()
        raise ValueError("Need an id or barcode to match a user.")

    def resolve_group(rec: dict) -> uuid.UUID | None:
        name = _text(rec.get("group"))
        if name is None:
            return None
        group = groups_by_name.get(name)
        if group is None:
            raise ValueError(f"Unknown group {name!r}.")
        return group.id

    for number, rec in _read_rows(content):
        action = (_text(rec.get("action")) or "").upper()
        try:
            if not action:
                result.skipped += 1
            elif action == "C":
                name = _text(rec.get("name"))
                if not name:
                    raise ValueError("Name is required to create a user.")
                user = User(
                    name=name,
                    group_id=resolve_group(rec),
                    status=_parse_enum(UserStatus, rec.get("status") or "Active", "status"),
                    barcode=await _resolve_barcode(
                        session, User, barcode_svc.USER_PREFIX, _text(rec.get("barcode"))
                    ),
                )
                session.add(user)
                await session.flush()
                result.created += 1
            elif action == "U":
                user = await find(rec)
                if user is None:
                    raise ValueError("No matching user to update.")
                if _text(rec.get("name")):
                    user.name = _text(rec["name"])
                if "group" in rec:
                    user.group_id = resolve_group(rec)
                if _text(rec.get("status")):
                    user.status = _parse_enum(UserStatus, rec["status"], "status")
                if _text(rec.get("barcode")):
                    user.barcode = await _resolve_barcode(
                        session, User, barcode_svc.USER_PREFIX, _text(rec["barcode"]), user.barcode
                    )
                session.add(user)
                result.updated += 1
            elif action == "D":
                user = await find(rec)
                if user is None:
                    raise ValueError("No matching user to delete.")
                await session.execute(
                    update(Event).where(Event.user_id == user.id).values(user_id=None)
                )
                await session.delete(user)
                result.deleted += 1
            else:
                raise ValueError(f"Unknown action {action!r} (use C, U, or D).")
        except ValueError as exc:
            result.errors.append(RowError(row=number, message=str(exc)))

    await session.commit()
    return result


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------
async def items_workbook(session: AsyncSession) -> bytes:
    types = {t.id: t.name for t in (await session.execute(select(ItemType))).scalars()}
    items = (await session.execute(select(Item).order_by(Item.name))).scalars()
    rows = [
        [
            "",
            str(i.id),
            i.barcode,
            i.name,
            types.get(i.item_type_id, ""),
            i.location or "",
            str(i.condition),
            i.needs_review,
        ]
        for i in items
    ]
    return _workbook_bytes(ITEM_HEADERS, rows)


async def import_items(session: AsyncSession, content: bytes) -> ImportResult:
    result = ImportResult()
    types_by_name = {t.name: t for t in (await session.execute(select(ItemType))).scalars()}

    async def find(rec: dict) -> Item | None:
        if _text(rec.get("id")):
            return await session.get(Item, _parse_uuid(rec["id"], "id"))
        code = _text(rec.get("barcode"))
        if code:
            return (
                await session.execute(select(Item).where(Item.barcode == code))
            ).scalar_one_or_none()
        raise ValueError("Need an id or barcode to match an item.")

    def resolve_type(rec: dict) -> uuid.UUID:
        name = _text(rec.get("item_type"))
        if name is None:
            raise ValueError("item_type is required.")
        item_type = types_by_name.get(name)
        if item_type is None:
            raise ValueError(f"Unknown item type {name!r}.")
        return item_type.id

    for number, rec in _read_rows(content):
        action = (_text(rec.get("action")) or "").upper()
        try:
            if not action:
                result.skipped += 1
            elif action == "C":
                name = _text(rec.get("name"))
                if not name:
                    raise ValueError("Name is required to create an item.")
                item = Item(
                    name=name,
                    item_type_id=resolve_type(rec),
                    location=_text(rec.get("location")),
                    condition=_parse_enum(Condition, rec.get("condition") or "New", "condition"),
                    needs_review=_parse_bool(rec.get("needs_review")),
                    barcode=await _resolve_barcode(
                        session, Item, barcode_svc.ITEM_PREFIX, _text(rec.get("barcode"))
                    ),
                )
                session.add(item)
                await session.flush()
                session.add(Event(item_id=item.id, event_type=EventType.CREATE))
                result.created += 1
            elif action == "U":
                item = await find(rec)
                if item is None:
                    raise ValueError("No matching item to update.")
                if _text(rec.get("name")):
                    item.name = _text(rec["name"])
                if _text(rec.get("item_type")):
                    item.item_type_id = resolve_type(rec)
                if "location" in rec:
                    item.location = _text(rec.get("location"))
                if _text(rec.get("condition")):
                    item.condition = _parse_enum(Condition, rec["condition"], "condition")
                if _text(rec.get("needs_review")) is not None:
                    item.needs_review = _parse_bool(rec.get("needs_review"))
                if _text(rec.get("barcode")):
                    item.barcode = await _resolve_barcode(
                        session, Item, barcode_svc.ITEM_PREFIX, _text(rec["barcode"]), item.barcode
                    )
                session.add(item)
                result.updated += 1
            elif action == "D":
                item = await find(rec)
                if item is None:
                    raise ValueError("No matching item to delete.")
                await session.execute(delete(Event).where(Event.item_id == item.id))
                await session.delete(item)
                result.deleted += 1
            else:
                raise ValueError(f"Unknown action {action!r} (use C, U, or D).")
        except ValueError as exc:
            result.errors.append(RowError(row=number, message=str(exc)))

    await session.commit()
    return result
