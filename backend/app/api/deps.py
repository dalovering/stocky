"""Shared API dependencies and helpers."""

from __future__ import annotations

from fastapi import Cookie, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_admin_token
from app.services import barcode as barcode_svc


async def require_admin(
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie),
) -> None:
    """Guard admin routes: require a valid admin session cookie."""
    if not session_cookie or not decode_admin_token(session_cookie):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
        )


async def ensure_unique_barcode(
    session: AsyncSession,
    model: type,
    prefix: str,
    proposed: str | None,
) -> str:
    """Return a barcode unique within `model`'s table, mapping conflicts to HTTP 409.

    Thin API-layer wrapper over `barcode.allocate_barcode` (the shared allocation logic).
    """
    try:
        return await barcode_svc.allocate_barcode(session, model, prefix, proposed)
    except barcode_svc.BarcodeConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
