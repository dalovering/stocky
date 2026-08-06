"""Admin: cross-entity exports (the full-database workbook)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.api.responses import xlsx_response
from app.core.db import get_session
from app.services import spreadsheet

router = APIRouter(
    prefix="/api/admin", tags=["admin:export"], dependencies=[Depends(require_admin)]
)


@router.get("/database.xlsx")
async def export_database(session: AsyncSession = Depends(get_session)) -> Response:
    """The whole database as one workbook: users, groups, item_types, items, history, settings.

    The settings sheet contains only the declared AppSettings keys — never the admin password
    hash, which shares the settings table (see spreadsheet.full_workbook).
    """
    return xlsx_response(await spreadsheet.full_workbook(session), "stocky-database.xlsx")
