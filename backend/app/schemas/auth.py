from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str


class SetupRequest(BaseModel):
    """First-launch admin password setup — only accepted while none is configured yet."""

    password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AuthStatus(BaseModel):
    authenticated: bool
    # True until an admin password has ever been set up; the frontend routes to /setup instead
    # of /login while this is true.
    needs_setup: bool = False
