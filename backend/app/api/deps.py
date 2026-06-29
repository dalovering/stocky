"""Shared API dependencies and helpers."""

from __future__ import annotations

from fastapi import Cookie, HTTPException, status
from sqlalchemy import select
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
    """Return a barcode unique within `model`'s table.

    Validates a proposed value (409 if taken) or generates a fresh one with `prefix`. Shared by
    the user and item admin routers — the only difference between them is the table and prefix.
    """
    if proposed:
        existing = await session.execute(select(model).where(model.barcode == proposed))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Barcode already in use.")
        return proposed
    for _ in range(10):
        code = barcode_svc.generate_code(prefix)
        existing = await session.execute(select(model).where(model.barcode == code))
        if existing.scalar_one_or_none() is None:
            return code
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not allocate a barcode.")
