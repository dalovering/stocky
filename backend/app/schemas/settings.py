"""Admin-configurable application settings."""

from __future__ import annotations

from functools import lru_cache
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings as env


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

    # --- Label printer (Nelko PM220, TSPL2) ---
    # Master switch: gates the print endpoints and all label-printer UI. The device path
    # itself is env config (PRINTER_DEVICE), not a setting — a DB-editable device path
    # would let any admin session point raw writes at an arbitrary file.
    # UNSET means "follow the wiring": on when a PRINTER_DEVICE is configured, off when
    # not — so configuring the printer (make init-env) is enough and no Settings visit is
    # needed. Once an admin toggles it, the stored value wins. default_factory re-reads
    # the env each load, so changing PRINTER_DEVICE updates the effective default.
    printer_enabled: bool = Field(default_factory=lambda: bool(env.printer_device))
    # The loaded label stock, in mm. These describe the roll (a consumable — editable
    # here, no redeploy), while the head caps printable width at 48 mm regardless.
    label_width_mm: float = Field(default=50.0, gt=0, le=54)
    label_height_mm: float = Field(default=30.0, gt=0, le=200)
    # Gap between die-cut labels (TSPL GAP) — the printer's gap sensor uses this to find the
    # label edge, so a wrong value mis-registers or mis-feeds. 6 mm matches Nelko's own rolls
    # (and the hardware capture the TSPL encoder is pinned to). Measure your stock if unsure.
    label_gap_mm: float = Field(default=6.0, ge=0, le=20)
    # Print darkness (TSPL DENSITY 0-15). 10 is the hardware-verified default.
    label_density: int = Field(default=10, ge=0, le=15)

    @field_validator("timezone")
    @classmethod
    def _valid_iana_zone(cls, value: str) -> str:
        if value not in _known_zones():
            raise ValueError(f"Unknown IANA time zone: {value!r}")
        return value


class VersionInfo(BaseModel):
    """The backend image's build identity (git describe + short commit)."""

    version: str
    commit: str


class AppSettingsUpdate(BaseModel):
    """A partial settings update — only the provided fields are changed."""

    kiosk_block_inactive_users: bool | None = None
    kiosk_idle_timeout_seconds: int | None = Field(default=None, ge=0, le=3600)
    admin_idle_timeout_minutes: int | None = Field(default=None, ge=0, le=480)
    timezone: str | None = None
    printer_enabled: bool | None = None
    label_width_mm: float | None = Field(default=None, gt=0, le=54)
    label_height_mm: float | None = Field(default=None, gt=0, le=200)
    label_gap_mm: float | None = Field(default=None, ge=0, le=20)
    label_density: int | None = Field(default=None, ge=0, le=15)

    @field_validator("timezone")
    @classmethod
    def _valid_iana_zone(cls, value: str | None) -> str | None:
        if value is not None and value not in _known_zones():
            raise ValueError(f"Unknown IANA time zone: {value!r}")
        return value
