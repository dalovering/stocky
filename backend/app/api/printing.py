"""Admin: rasterized label printing for the thermal label printer (Nelko PM220).

Previews return the *exact* 1-bit raster the print head receives, as a PNG rendered from
real rows at the configured label size — what you see is bit-for-bit what prints. The
whole surface lives under `/print/…` and `/printer…`, so nothing here can collide with
the `/{item_id}`-style routes in the inventory/users routers.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.api.responses import png_response
from app.core.db import get_session
from app.models import Item, User
from app.services import cards as cards_svc
from app.services import label_raster as raster
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
