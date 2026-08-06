"""The admin password hash: a single value kept in the `settings` key/value table.

Kept separate from `services/settings.py` (the `AppSettings` document returned to the admin UI)
so the hash is never at risk of being serialized through that generic read/write path.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import Setting

_KEY = "admin_password_hash"


async def get_password_hash(session: AsyncSession) -> str | None:
    row = await session.get(Setting, _KEY)
    return row.value if row else None


async def is_configured(session: AsyncSession) -> bool:
    """True once an admin password has been set up."""
    return await get_password_hash(session) is not None


async def set_password(session: AsyncSession, password: str) -> None:
    row = await session.get(Setting, _KEY)
    value = hash_password(password)
    if row is None:
        session.add(Setting(key=_KEY, value=value))
    else:
        row.value = value
        session.add(row)
    await session.commit()


async def verify(session: AsyncSession, password: str) -> bool:
    stored = await get_password_hash(session)
    return stored is not None and verify_password(password, stored)
