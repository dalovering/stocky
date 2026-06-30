"""Kiosk: barcode-driven check-in/out. Open on the trusted LAN (no admin auth)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Event, Item, User, UserStatus
from app.schemas.inventory import EventRead, ItemRead
from app.schemas.kiosk import (
    ItemActionRequest,
    ScanAction,
    ScanKind,
    ScanRequest,
    ScanResponse,
)
from app.schemas.user import UserDetail
from app.services import events as event_svc
from app.services import settings as settings_svc
from app.services.serialize import serialize_event, serialize_item, serialize_user_detail
from app.services.status import latest_checkout_holder

router = APIRouter(prefix="/api/kiosk", tags=["kiosk"])


async def _user_by_barcode(session: AsyncSession, code: str) -> User | None:
    return (await session.execute(select(User).where(User.barcode == code))).scalar_one_or_none()


async def _is_blocked(session: AsyncSession, user: User) -> bool:
    """Whether this user is barred from the kiosk (inactive + the setting is enabled)."""
    if user.status != UserStatus.INACTIVE:
        return False
    return await settings_svc.kiosk_blocks_inactive(session)


async def _item_by_barcode(session: AsyncSession, code: str) -> Item | None:
    return (await session.execute(select(Item).where(Item.barcode == code))).scalar_one_or_none()


@router.post("/scan", response_model=ScanResponse)
async def scan(body: ScanRequest, session: AsyncSession = Depends(get_session)) -> ScanResponse:
    """Resolve a scanned barcode and decide what the kiosk should do.

    - A user barcode logs that user in (or switches users).
    - An item barcode, with an active user, passively checks the item out or in:
        * not on loan            -> check out to the active user
        * on loan to active user -> check in
        * on loan to someone else-> open the item modal (ambiguous)
    - With no active user, an item scan returns the item so the UI can open its modal.
    """
    code = body.barcode.strip()

    user = await _user_by_barcode(session, code)
    if user is not None:
        if await _is_blocked(session, user):
            return ScanResponse(
                kind=ScanKind.USER,
                action=ScanAction.UNKNOWN,
                message=f"{user.name} is inactive and can't use the kiosk.",
            )
        return ScanResponse(
            kind=ScanKind.USER,
            action=ScanAction.LOGIN,
            message=f"Logged in as {user.name}.",
            user=await serialize_user_detail(session, user),
        )

    item = await _item_by_barcode(session, code)
    if item is None:
        return ScanResponse(
            kind=ScanKind.UNKNOWN,
            action=ScanAction.UNKNOWN,
            message="Unrecognized barcode.",
        )

    if body.active_user_id is None:
        return ScanResponse(
            kind=ScanKind.ITEM,
            action=ScanAction.OPEN_MODAL,
            message="Scan a student ID first, or use the item actions.",
            item=await serialize_item(session, item),
        )

    holder = await latest_checkout_holder(session, item.id)
    try:
        if holder is None:
            await event_svc.check_out(session, item, body.active_user_id)
            action, msg = ScanAction.CHECKED_OUT, f"Checked out {item.name}."
        elif holder == body.active_user_id:
            await event_svc.check_in(session, item, body.active_user_id)
            action, msg = ScanAction.CHECKED_IN, f"Checked in {item.name}."
        else:
            # Held by another user — let the operator decide via the modal.
            return ScanResponse(
                kind=ScanKind.ITEM,
                action=ScanAction.OPEN_MODAL,
                message=f"{item.name} is checked out by another user.",
                item=await serialize_item(session, item),
            )
    except event_svc.LoanError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await session.commit()
    await session.refresh(item)
    return ScanResponse(
        kind=ScanKind.ITEM,
        action=action,
        message=msg,
        item=await serialize_item(session, item),
    )


async def _load_item(session: AsyncSession, item_id: uuid.UUID) -> Item:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    return item


def _require_user_id(body: ItemActionRequest) -> uuid.UUID:
    if body.user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A user is required for this action.")
    return body.user_id


@router.post("/checkout", response_model=ItemRead)
async def checkout(
    body: ItemActionRequest, session: AsyncSession = Depends(get_session)
) -> ItemRead:
    item = await _load_item(session, body.item_id)
    user_id = _require_user_id(body)
    user = await session.get(User, user_id)
    if user is not None and await _is_blocked(session, user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"{user.name} is inactive and can't check out items."
        )
    try:
        await event_svc.check_out(session, item, user_id)
    except event_svc.LoanError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(item)
    return await serialize_item(session, item)


@router.post("/checkin", response_model=ItemRead)
async def checkin(
    body: ItemActionRequest, session: AsyncSession = Depends(get_session)
) -> ItemRead:
    item = await _load_item(session, body.item_id)
    try:
        await event_svc.check_in(session, item, _require_user_id(body))
    except event_svc.LoanError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await session.commit()
    await session.refresh(item)
    return await serialize_item(session, item)


@router.post("/report-damage", response_model=ItemRead)
async def report_damage(
    body: ItemActionRequest, session: AsyncSession = Depends(get_session)
) -> ItemRead:
    item = await _load_item(session, body.item_id)
    await event_svc.report_damage(session, item, body.user_id, body.note)
    await session.commit()
    await session.refresh(item)
    return await serialize_item(session, item)


@router.post("/report-loss", response_model=ItemRead)
async def report_loss(
    body: ItemActionRequest, session: AsyncSession = Depends(get_session)
) -> ItemRead:
    item = await _load_item(session, body.item_id)
    await event_svc.report_loss(session, item, body.user_id, body.note)
    await session.commit()
    await session.refresh(item)
    return await serialize_item(session, item)


@router.get("/user/{user_id}", response_model=UserDetail)
async def kiosk_user(
    user_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> UserDetail:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return await serialize_user_detail(session, user)


@router.get("/user/{user_id}/events", response_model=list[EventRead])
async def kiosk_user_events(
    user_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[EventRead]:
    """The logged-in user's event history at the kiosk, most recent first."""
    result = await session.execute(
        select(Event).where(Event.user_id == user_id).order_by(Event.created_at.desc())
    )
    return [await serialize_event(session, e) for e in result.scalars().all()]
