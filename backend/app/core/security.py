"""Admin authentication: password hashing + signed-JWT session cookie."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """Hash a password for storage. Never store or compare plaintext."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Check a password against a hash produced by `hash_password`."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


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
