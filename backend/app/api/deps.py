"""Shared API dependencies."""

from __future__ import annotations

from fastapi import Cookie, HTTPException, status

from app.core.config import settings
from app.core.security import decode_admin_token


async def require_admin(
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie),
) -> None:
    """Guard admin routes: require a valid admin session cookie."""
    if not session_cookie or not decode_admin_token(session_cookie):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required.",
        )
