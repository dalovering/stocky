"""Read and write the app-level settings document.

Settings are stored one row per key in the `settings` table; this module is the typed gateway,
applying defaults from `AppSettings` for any key that hasn't been written yet.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Setting
from app.schemas.settings import AppSettings, AppSettingsUpdate


async def load_settings(session: AsyncSession) -> AppSettings:
    """The current settings, with defaults filled in for unset keys."""
    stored = {s.key: s.value for s in (await session.execute(select(Setting))).scalars()}
    known = {k: stored[k] for k in AppSettings.model_fields if k in stored}
    return AppSettings(**known)


async def save_settings(session: AsyncSession, update: AppSettingsUpdate) -> AppSettings:
    """Upsert the provided settings keys and return the full, current document."""
    for key, value in update.model_dump(exclude_unset=True).items():
        row = await session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
            session.add(row)
    await session.commit()
    return await load_settings(session)


async def kiosk_blocks_inactive(session: AsyncSession) -> bool:
    return (await load_settings(session)).kiosk_block_inactive_users


async def app_timezone(session: AsyncSession) -> str:
    """The IANA zone for local-day bucketing (attendance) and export timestamps."""
    return (await load_settings(session)).timezone
