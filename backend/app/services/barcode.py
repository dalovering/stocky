"""Barcode value generation and allocation.

Codes are random 10-digit values with a 1-char namespace prefix (`U`/`I`), encoded as Code128 on
the printed cards (the symbology cheap USB kiosk scanners read — rendered at print time by
`services/cards.py`). This module only mints and reserves unique *values*; no barcode library is
needed.
"""

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Prefixes keep user and item barcodes in distinct namespaces, though resolution is by lookup.
USER_PREFIX = "U"
ITEM_PREFIX = "I"


class BarcodeConflict(Exception):
    """A requested barcode is already in use, or none could be allocated."""


def generate_code(prefix: str) -> str:
    """Generate a random, hard-to-collide barcode value, e.g. 'U0427193855'."""
    digits = "".join(secrets.choice("0123456789") for _ in range(10))
    return f"{prefix}{digits}"


def generate_user_code() -> str:
    return generate_code(USER_PREFIX)


def generate_item_code() -> str:
    return generate_code(ITEM_PREFIX)


async def allocate_barcode(
    session: AsyncSession,
    model: type,
    prefix: str,
    proposed: str | None = None,
    current: str | None = None,
) -> str:
    """Return a unique barcode for `model`.

    Validate a `proposed` value (raise `BarcodeConflict` if taken), reuse `current` when unchanged,
    or generate a fresh prefixed value. Shared by the admin API and the xlsx importer so both
    enforce uniqueness identically.
    """
    if proposed:
        if proposed == current:
            return proposed
        taken = (
            await session.execute(select(model).where(model.barcode == proposed))
        ).scalar_one_or_none()
        if taken is not None:
            raise BarcodeConflict(f"Barcode {proposed!r} already in use.")
        return proposed
    if current:
        return current
    for _ in range(10):
        code = generate_code(prefix)
        exists = (
            await session.execute(select(model).where(model.barcode == code))
        ).scalar_one_or_none()
        if exists is None:
            return code
    raise BarcodeConflict("Could not allocate a unique barcode.")
