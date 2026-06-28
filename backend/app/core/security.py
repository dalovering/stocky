"""Admin authentication: password check + signed-JWT session cookie."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings


def verify_admin_password(password: str) -> bool:
    """Constant-time comparison against the configured admin password."""
    return hmac.compare_digest(password.encode(), settings.admin_password.encode())


def create_admin_token() -> str:
    """Create a signed JWT marking the bearer as an authenticated admin."""
    now = datetime.now(UTC)
    payload = {
        "sub": "admin",
        "role": "admin",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_admin_token(token: str) -> bool:
    """Return True if `token` is a valid, unexpired admin session token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return False
    return payload.get("role") == "admin"
