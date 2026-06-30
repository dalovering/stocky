"""Admin: a multi-up troubleshooting sheet of every ID card and item tag.

One US-Letter PDF with two sections — all user ID cards, then all item tags — using the same SVG
templates as the single/per-group prints. Handy for bulk printing or checking the templates.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.api.responses import pdf_response
from app.core.db import get_session
from app.models import Item, User
from app.services import cards as cards_svc

router = APIRouter(
    prefix="/api/admin", tags=["admin:labels"], dependencies=[Depends(require_admin)]
)


@router.get("/labels.pdf")
async def labels_pdf(session: AsyncSession = Depends(get_session)) -> Response:
    """Render the multi-up sheet: every user ID card, then every item tag."""
    users = list((await session.execute(select(User).order_by(User.name))).scalars())
    items = list((await session.execute(select(Item).order_by(Item.name))).scalars())
    pdf = cards_svc.render_multi_up(
        await cards_svc.build_user_cards(session, users),
        await cards_svc.build_item_cards(session, items),
    )
    return pdf_response(pdf, "stocky-cards.pdf")
