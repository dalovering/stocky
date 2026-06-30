"""Admin: a multi-up troubleshooting sheet of every ID card and item tag.

One US-Letter PDF with two sections — all user ID cards, then all item tags — using the same SVG
templates as the single/per-group prints. Handy for bulk printing or checking the templates.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_session
from app.models import Group, Item, ItemType, User
from app.services import cards as cards_svc

router = APIRouter(
    prefix="/api/admin", tags=["admin:labels"], dependencies=[Depends(require_admin)]
)


@router.get("/labels.pdf")
async def labels_pdf(session: AsyncSession = Depends(get_session)) -> Response:
    """Render the multi-up sheet: every user ID card, then every item tag."""
    group_names = {g.id: g.name for g in (await session.execute(select(Group))).scalars()}
    users = (await session.execute(select(User).order_by(User.name))).scalars()
    id_cards = [
        cards_svc.CardData(
            title=u.name, subtitle=group_names.get(u.group_id), extra=None, barcode=u.barcode
        )
        for u in users
    ]

    type_names = {t.id: t.name for t in (await session.execute(select(ItemType))).scalars()}
    items = (await session.execute(select(Item).order_by(Item.name))).scalars()
    item_tags = [
        cards_svc.CardData(
            title=i.name,
            subtitle=type_names.get(i.item_type_id),
            extra=i.location,
            barcode=i.barcode,
        )
        for i in items
    ]

    pdf = cards_svc.render_multi_up(id_cards, item_tags)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="stocky-cards.pdf"'},
    )
