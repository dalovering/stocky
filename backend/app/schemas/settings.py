"""Admin-configurable application settings."""

from __future__ import annotations

from pydantic import BaseModel


class AppSettings(BaseModel):
    """The full settings document, with defaults for anything not stored yet."""

    # When true, an Inactive user is rejected at the kiosk (can't log in or check out).
    kiosk_block_inactive_users: bool = False


class AppSettingsUpdate(BaseModel):
    """A partial settings update — only the provided fields are changed."""

    kiosk_block_inactive_users: bool | None = None
