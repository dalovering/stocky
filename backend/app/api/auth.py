"""Admin authentication routes: first-launch setup, login/logout, and password changes."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import settings
from app.core.db import get_session
from app.core.security import create_admin_token, decode_admin_token
from app.schemas.auth import AuthStatus, ChangePasswordRequest, LoginRequest, SetupRequest
from app.services import admin_auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _start_session(response: Response) -> None:
    token = create_admin_token()
    response.set_cookie(
        key=settings.session_cookie,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )


@router.post("/setup", response_model=AuthStatus)
async def setup(
    body: SetupRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthStatus:
    """Set the admin password on first launch. Rejected once a password is already configured."""
    if await admin_auth.is_configured(session):
        raise HTTPException(status.HTTP_409_CONFLICT, "Admin password is already configured.")
    await admin_auth.set_password(session, body.password)
    _start_session(response)
    return AuthStatus(authenticated=True, needs_setup=False)


@router.post("/login", response_model=AuthStatus)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthStatus:
    if not await admin_auth.is_configured(session):
        raise HTTPException(status.HTTP_409_CONFLICT, "Admin password has not been set up yet.")
    if not await admin_auth.verify(session, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect admin password.")
    _start_session(response)
    return AuthStatus(authenticated=True)


@router.post("/logout", response_model=AuthStatus)
async def logout(response: Response) -> AuthStatus:
    response.delete_cookie(settings.session_cookie)
    return AuthStatus(authenticated=False)


@router.get("/status", response_model=AuthStatus)
async def auth_status(
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie),
    session: AsyncSession = Depends(get_session),
) -> AuthStatus:
    authenticated = bool(session_cookie and decode_admin_token(session_cookie))
    needs_setup = not await admin_auth.is_configured(session)
    return AuthStatus(authenticated=authenticated, needs_setup=needs_setup)


@router.post("/change-password", response_model=AuthStatus)
async def change_password(
    body: ChangePasswordRequest,
    session: AsyncSession = Depends(get_session),
    _admin: None = Depends(require_admin),
) -> AuthStatus:
    if not await admin_auth.verify(session, body.current_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect.")
    await admin_auth.set_password(session, body.new_password)
    return AuthStatus(authenticated=True)
