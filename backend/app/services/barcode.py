"""Barcode value generation and Code128 SVG rendering.

Used for printable user ID cards and item tags. Code128 is widely supported by cheap USB
barcode scanners (which the kiosk targets) and encodes alphanumeric values compactly.
"""

from __future__ import annotations

import secrets
from io import BytesIO

import barcode
from barcode.writer import SVGWriter

# Prefixes keep user and item barcodes in distinct namespaces, though resolution is by lookup.
USER_PREFIX = "U"
ITEM_PREFIX = "I"


def generate_code(prefix: str) -> str:
    """Generate a random, hard-to-collide barcode value, e.g. 'U0427193855'."""
    digits = "".join(secrets.choice("0123456789") for _ in range(10))
    return f"{prefix}{digits}"


def generate_user_code() -> str:
    return generate_code(USER_PREFIX)


def generate_item_code() -> str:
    return generate_code(ITEM_PREFIX)


def render_svg(value: str) -> str:
    """Render `value` as a Code128 barcode and return it as an SVG string."""
    code128 = barcode.get("code128", value, writer=SVGWriter())
    buffer = BytesIO()
    code128.write(buffer)
    return buffer.getvalue().decode("utf-8")
