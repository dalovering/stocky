"""Admin: rasterized label printing for the thermal label printer (Nelko PM220).

Previews return the *exact* 1-bit raster the print head receives, as a PNG rendered from
real rows at the configured label size — what you see is bit-for-bit what prints. The
whole surface lives under `/print/…` and `/printer…`, so nothing here can collide with
the `/{item_id}`-style routes in the inventory/users routers.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.api.responses import png_response
from app.core.config import settings as app_config
from app.core.db import get_session
from app.models import Item, User
from app.schemas.printing import PrinterInfo, PrinterState
from app.services import cards as cards_svc
from app.services import label_raster as raster
from app.services import printer as printer_svc
from app.services import settings as settings_svc
from app.services.cards import CardData
from app.services.tspl import LabelGeometry

router = APIRouter(
    prefix="/api/admin", tags=["admin:printing"], dependencies=[Depends(require_admin)]
)


async def _label_geometry(session: AsyncSession) -> LabelGeometry:
    app_settings = await settings_svc.load_settings(session)
    return LabelGeometry(
        width_mm=app_settings.label_width_mm, height_mm=app_settings.label_height_mm
    )


def _probe_state(status_report: printer_svc.ProbeReport) -> tuple[PrinterState, str]:
    if status_report.error is not None:
        return PrinterState.UNREACHABLE, status_report.error
    status = status_report.status
    assert status is not None
    if status.out_of_paper:
        return PrinterState.NO_PAPER, "Load a roll and close the lid."
    if status.lid_open:
        return PrinterState.LID_OPEN, "Close the lid."
    if status.busy:
        return PrinterState.BUSY, "The printer is printing."
    if status.flags != 0:
        return PrinterState.ERROR, f"The printer reported status 0x{status.flags:02x}."
    return PrinterState.READY, "The printer is ready."


@router.get("/printer", response_model=PrinterInfo)
async def printer_info(
    probe: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> PrinterInfo:
    """Printer configuration, and — with ?probe=true — a live status/battery read.

    The default (no probe) does zero device I/O, so list pages can gate their print
    buttons on it cheaply.
    """
    app_settings = await settings_svc.load_settings(session)
    configured = bool(app_config.printer_device)
    info = PrinterInfo(
        configured=configured,
        enabled=app_settings.printer_enabled,
        device=app_config.printer_device or None,
        transport=app_config.printer_transport,
        state=PrinterState.NOT_CONFIGURED if not configured else PrinterState.NOT_CHECKED,
        message="Set PRINTER_DEVICE in .env to enable label printing." if not configured else "",
        label_width_mm=app_settings.label_width_mm,
        label_height_mm=app_settings.label_height_mm,
        label_gap_mm=app_settings.label_gap_mm,
        label_density=app_settings.label_density,
        max_batch=printer_svc.MAX_BATCH_LABELS,
    )
    if not (probe and configured):
        return info
    report = await printer_svc.probe()
    state, message = _probe_state(report)
    update = {"state": state, "message": message, "battery_percent": report.battery_percent}
    if report.status is not None:
        update["roll_width_mm"] = report.status.label_width_mm or None
        update["roll_length_mm"] = report.status.label_length_mm or None
    return info.model_copy(update=update)


def _render_png(kind: raster.LabelKind, geometry: LabelGeometry, card: CardData) -> bytes:
    try:
        return raster.render_png(kind, geometry, card)
    except raster.LabelError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.get("/print/items/{item_id}/preview.png")
async def item_label_preview(
    item_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """The item's tag exactly as the printer will raster it."""
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found.")
    card = (await cards_svc.build_item_cards(session, [item]))[0]
    png = _render_png(raster.LabelKind.ITEM_TAG, await _label_geometry(session), card)
    return png_response(png, f"label-{item.barcode}.png")


@router.get("/print/users/{user_id}/preview.png")
async def user_label_preview(
    user_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """The user's badge exactly as the printer will raster it."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    card = (await cards_svc.build_user_cards(session, [user]))[0]
    png = _render_png(raster.LabelKind.USER_BADGE, await _label_geometry(session), card)
    return png_response(png, f"badge-{user.barcode}.png")
