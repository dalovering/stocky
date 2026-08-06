"""Admin-configurable application settings."""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator


@lru_cache(maxsize=1)
def _known_zones() -> frozenset[str]:
    # available_timezones() walks the tz database on disk — do it once, not per validation.
    return frozenset(available_timezones())


class AppSettings(BaseModel):
    """The full settings document, with defaults for anything not stored yet."""

    # When true, an Inactive user is rejected at the kiosk (can't log in or check out).
    kiosk_block_inactive_users: bool = False
    # Seconds of kiosk inactivity before the scanned-in user is logged out. 0 = never.
    kiosk_idle_timeout_seconds: int = Field(default=60, ge=0, le=3600)
    # Minutes of admin inactivity before the browser signs the admin out. 0 = never.
    # Enforced client-side; the JWT's absolute expiry (JWT_EXPIRE_MINUTES) still applies.
    admin_idle_timeout_minutes: int = Field(default=15, ge=0, le=480)
    # IANA zone used wherever Stocky needs a local calendar day or local timestamps
    # (attendance day bucketing, spreadsheet export timestamps).
    timezone: str = "America/New_York"

    @field_validator("timezone")
    @classmethod
    def _valid_iana_zone(cls, value: str) -> str:
        if value not in _known_zones():
            raise ValueError(f"Unknown IANA time zone: {value!r}")
        return value


class AppSettingsUpdate(BaseModel):
    """A partial settings update — only the provided fields are changed."""

    kiosk_block_inactive_users: bool | None = None
    kiosk_idle_timeout_seconds: int | None = Field(default=None, ge=0, le=3600)
    admin_idle_timeout_minutes: int | None = Field(default=None, ge=0, le=480)
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _valid_iana_zone(cls, value: str | None) -> str | None:
        if value is not None and value not in _known_zones():
            raise ValueError(f"Unknown IANA time zone: {value!r}")
        return value
