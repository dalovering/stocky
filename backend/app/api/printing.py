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
from app.api.responses import binary_response, png_response
from app.core.config import settings as app_config
from app.core.db import get_session
from app.models import Item, User
from app.schemas.inventory import IdList
from app.schemas.printing import PrinterInfo, PrinterState, PrintResult
from app.services import cards as cards_svc
from app.services import label_raster as raster
from app.services import printer as printer_svc
from app.services import queries
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
    state, message = printer_svc.describe_probe(report)
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


# ---------------------------------------------------------------------------
# Printing. POST everywhere — a print consumes paper, so no GET may trigger one
# (browser prefetch / retry would burn labels), and IdList collapses single row,
# selection, whole-type, and whole-group into one endpoint per label kind.
# ---------------------------------------------------------------------------


async def _print(
    kind: raster.LabelKind, cards: list[CardData], session: AsyncSession
) -> PrintResult:
    app_settings = await settings_svc.load_settings(session)
    try:
        outcome = await printer_svc.print_cards(kind, cards, app_settings)
    except (printer_svc.PrinterNotConfigured, printer_svc.PrinterNotReady) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except printer_svc.PrinterUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except raster.LabelError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return PrintResult(
        printed=outcome.printed,
        requested=outcome.requested,
        bytes_sent=outcome.bytes_sent,
        warnings=outcome.warnings,
    )


@router.post("/print/items", response_model=PrintResult)
async def print_item_tags(
    body: IdList, session: AsyncSession = Depends(get_session)
) -> PrintResult:
    """One tag per selected item (a single id prints a single tag)."""
    items = await queries.items_by_ids(session, body.ids)
    cards = await cards_svc.build_item_cards(session, items)
    return await _print(raster.LabelKind.ITEM_TAG, cards, session)


@router.post("/print/item-types", response_model=PrintResult)
async def print_item_type_tags(
    body: IdList, session: AsyncSession = Depends(get_session)
) -> PrintResult:
    """One tag per item of each selected type."""
    items = await queries.items_by_type_ids(session, body.ids)
    cards = await cards_svc.build_item_cards(session, items)
    return await _print(raster.LabelKind.ITEM_TAG, cards, session)


@router.post("/print/users", response_model=PrintResult)
async def print_user_badges(
    body: IdList, session: AsyncSession = Depends(get_session)
) -> PrintResult:
    """One badge per selected user."""
    users = await queries.users_by_ids(session, body.ids)
    cards = await cards_svc.build_user_cards(session, users)
    return await _print(raster.LabelKind.USER_BADGE, cards, session)


@router.post("/print/groups", response_model=PrintResult)
async def print_group_badges(
    body: IdList, session: AsyncSession = Depends(get_session)
) -> PrintResult:
    """One badge per direct member of each selected group (same scope as the PDF)."""
    users = await queries.users_by_group_ids(session, body.ids)
    cards = await cards_svc.build_user_cards(session, users)
    return await _print(raster.LabelKind.USER_BADGE, cards, session)


@router.post("/printer/test-print", response_model=PrintResult)
async def printer_test_print(session: AsyncSession = Depends(get_session)) -> PrintResult:
    """One calibration label (works while printing is disabled — it's the setup tool)."""
    app_settings = await settings_svc.load_settings(session)
    try:
        outcome = await printer_svc.print_test_label(app_settings)
    except (printer_svc.PrinterNotConfigured, printer_svc.PrinterNotReady) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except printer_svc.PrinterUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return PrintResult(
        printed=outcome.printed,
        requested=outcome.requested,
        bytes_sent=outcome.bytes_sent,
        warnings=outcome.warnings,
    )


# --- Raw TSPL job export: print without backend device access -------------------------
# The complete job as bytes, for a raw queue (`lp -o raw` on a Mac with the printer on
# USB) — and the seam a future in-browser Web Serial / Web Bluetooth transport would
# fetch. Pure computation: no device, no printer_enabled gate.


@router.post("/print/items/job.tspl")
async def item_tags_tspl_job(
    body: IdList, session: AsyncSession = Depends(get_session)
) -> Response:
    items = await queries.items_by_ids(session, body.ids)
    cards = await cards_svc.build_item_cards(session, items)
    return await _tspl_job(raster.LabelKind.ITEM_TAG, cards, session, "stocky-item-tags.tspl")


@router.post("/print/users/job.tspl")
async def user_badges_tspl_job(
    body: IdList, session: AsyncSession = Depends(get_session)
) -> Response:
    users = await queries.users_by_ids(session, body.ids)
    cards = await cards_svc.build_user_cards(session, users)
    return await _tspl_job(raster.LabelKind.USER_BADGE, cards, session, "stocky-badges.tspl")


async def _tspl_job(
    kind: raster.LabelKind, cards: list[CardData], session: AsyncSession, filename: str
) -> Response:
    app_settings = await settings_svc.load_settings(session)
    try:
        job = printer_svc.encode_cards_job(kind, cards, app_settings)
    except raster.LabelError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return binary_response(job, filename)
