"""Admin: printable barcode-label sheets (PDF) for users and inventory.

One endpoint renders every user's ID-card barcode and every item's tag barcode into a single
PDF with two sections, so an admin can print the whole set in one go.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_session
from app.models import Group, Item, ItemType, User
from app.services import labels as labels_svc

router = APIRouter(
    prefix="/api/admin", tags=["admin:labels"], dependencies=[Depends(require_admin)]
)


@router.get("/labels.pdf")
async def labels_pdf(session: AsyncSession = Depends(get_session)) -> Response:
    """Render a two-section barcode-label PDF: all users, then all inventory items."""
    users = (await session.execute(select(User).order_by(User.name))).scalars().all()
    group_names = {g.id: g.name for g in (await session.execute(select(Group))).scalars().all()}
    user_labels = [
        labels_svc.Label(title=u.name, subtitle=group_names.get(u.group_id), barcode=u.barcode)
        for u in users
    ]

    items = (await session.execute(select(Item).order_by(Item.name))).scalars().all()
    type_names = {t.id: t.name for t in (await session.execute(select(ItemType))).scalars().all()}
    item_labels = [
        labels_svc.Label(title=i.name, subtitle=type_names.get(i.item_type_id), barcode=i.barcode)
        for i in items
    ]

    pdf = labels_svc.render_label_sheet(user_labels, item_labels)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="stocky-barcode-labels.pdf"'},
    )
