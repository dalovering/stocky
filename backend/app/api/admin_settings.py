"""Admin: read and update app-level settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_session
from app.schemas.settings import AppSettings, AppSettingsUpdate
from app.services import settings as settings_svc

router = APIRouter(
    prefix="/api/admin", tags=["admin:settings"], dependencies=[Depends(require_admin)]
)


@router.get("/settings", response_model=AppSettings)
async def get_settings(session: AsyncSession = Depends(get_session)) -> AppSettings:
    return await settings_svc.load_settings(session)


@router.patch("/settings", response_model=AppSettings)
async def update_settings(
    body: AppSettingsUpdate, session: AsyncSession = Depends(get_session)
) -> AppSettings:
    return await settings_svc.save_settings(session, body)
