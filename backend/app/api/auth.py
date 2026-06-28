"""Admin authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.core.config import settings
from app.core.security import create_admin_token, decode_admin_token, verify_admin_password
from app.schemas.auth import AuthStatus, LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=AuthStatus)
async def login(body: LoginRequest, response: Response) -> AuthStatus:
    if not verify_admin_password(body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect admin password.")
    token = create_admin_token()
    response.set_cookie(
        key=settings.session_cookie,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
    )
    return AuthStatus(authenticated=True)


@router.post("/logout", response_model=AuthStatus)
async def logout(response: Response) -> AuthStatus:
    response.delete_cookie(settings.session_cookie)
    return AuthStatus(authenticated=False)


@router.get("/status", response_model=AuthStatus)
async def auth_status(
    session_cookie: str | None = Cookie(default=None, alias=settings.session_cookie),
) -> AuthStatus:
    return AuthStatus(authenticated=bool(session_cookie and decode_admin_token(session_cookie)))
