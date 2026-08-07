"""1-bit label rasterization for the thermal label printer.

The printer's native `BARCODE` command is broken (see `services/tspl.py`), so labels are
composed here as Pillow mode-"1" images and shipped as TSPL `BITMAP` payloads. A mode-"1"
image's `tobytes()` is *exactly* the BITMAP wire format (row-major, MSB first, bit 0 =
black), so there is no packing step.

This deliberately does NOT reuse the SVG templates that drive the PDF cards
(`services/cards.py`). Rasterizing a vector layout onto a 203 dpi (8 dots/mm) grid means
resampling — gray glyph edges thresholded to ragged stems, and fractional barcode module
widths, which wreck scannability. Instead the layout is computed directly in printer dots:

- Code128 bars are drawn at an integer 2 dots/module (0.25 mm X-dim). 2 is the only
  workable value: 1 dot/module (0.125 mm = 4.9 mil) is below the Code128 floor and scans
  intermittently; 3 dots/module doesn't fit a Stocky barcode on even the widest (48 mm)
  printable width. When a barcode doesn't fit at 2 dots/module we raise `LabelTooNarrow`
  rather than degrade — an intermittently-scannable label is worse than an error.
- Text uses Pillow's embedded scalable font (Aileron, FreeType — no font files to bundle,
  Latin-1 coverage). Set LABEL_FONT_PATH to a .ttf for a wider charset. On a mode-"1"
  canvas Pillow renders glyphs unantialiased, which is what a thermal head needs.

Both label kinds consume the same `CardData` the PDF path uses, so a printed label and a
printed PDF can never disagree about an item or user.

The user badge is a small sibling of the CR80 ID card, not a replacement — CR80 is
85.6 mm wide and the head prints 48 mm, so the PDF ID card remains the full-size artifact.
Omitted from the badge by design: a photo (not in the data model), a solid header band
(burns heat, and inverted small text is illegible at 203 dpi), and a border rect (thermal
registration drift clips it).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.barcode.code128 import Code128

from app.core.config import settings
from app.services.cards import CardData
from app.services.tspl import LabelGeometry

MODULE_DOTS = 2  # dots per Code128 module — see module docstring; do not change casually.
QUIET_MODULES = 10  # Code128 spec minimum quiet zone on each side.

_SIDE_MARGIN = 8  # dots (1 mm)
_V_MARGIN = 6
_BAND_GAP = 4
_BAR_MIN = 56  # dots (7 mm) — minimum readable bar height for handheld scanners
_BAR_MAX = 96
_MIN_TEXT = 11  # dots — below this, glyphs lose their counters at 203 dpi


class LabelKind(StrEnum):
    ITEM_TAG = "item_tag"
    USER_BADGE = "user_badge"


class LabelError(Exception):
    """A label cannot be rendered as requested."""


class LabelTooNarrow(LabelError):
    """The barcode doesn't fit the printable width at the minimum scannable module size."""


# ---------------------------------------------------------------------------
# Code128 at integer dot positions
# ---------------------------------------------------------------------------


def code128_pattern(value: str) -> list[tuple[bool, int]]:
    """`[(is_bar, width_in_modules), ...]` from ReportLab's own Code128 encoder.

    ReportLab's `decomposed` string encodes bars as A-D (1-4 modules) and spaces as a-d;
    we reuse its encoder (symbol selection, check symbol) but do our own drawing so every
    bar edge lands on an integer dot.
    """
    barcode = Code128(value, quiet=0, barHeight=1)
    barcode._calculate()
    if not barcode.valid:
        raise LabelError(f"Value {value!r} cannot be encoded as Code128.")
    return [(c.isupper(), ord(c.lower()) - ord("a") + 1) for c in barcode.decomposed]


def code128_width_dots(value: str, module_dots: int = MODULE_DOTS) -> int:
    """Width of the bars alone (no quiet zones), in dots."""
    return sum(width for _, width in code128_pattern(value)) * module_dots


def draw_code128(
    draw: ImageDraw.ImageDraw,
    value: str,
    *,
    x: int,
    y: int,
    height_dots: int,
    module_dots: int = MODULE_DOTS,
) -> int:
    """Draw the bars with every edge on an integer dot; returns the drawn width in dots."""
    cursor = x
    for is_bar, modules in code128_pattern(value):
        width = modules * module_dots
        if is_bar:
            draw.rectangle([cursor, y, cursor + width - 1, y + height_dots - 1], fill=0)
        cursor += width
    return cursor - x


# ---------------------------------------------------------------------------
# Fonts and text
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _font(size: int, path: str = "") -> ImageFont.FreeTypeFont:
    if path:
        return ImageFont.truetype(path, size=size)
    return ImageFont.load_default(size=size)


def _text_font(size: int) -> ImageFont.FreeTypeFont:
    return _font(size, settings.label_font_path)


def _fitted(draw: ImageDraw.ImageDraw, text: str, size: int, max_width: int) -> tuple[str, int]:
    """Shrink the font (to the legibility floor), then ellipsize, until the text fits."""
    while size > _MIN_TEXT and draw.textlength(text, font=_text_font(size)) > max_width:
        size -= 1
    if draw.textlength(text, font=_text_font(size)) <= max_width:
        return text, size
    while text and draw.textlength(text + "...", font=_text_font(size)) > max_width:
        text = text[:-1]
    return text + "...", size


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    center_x: int,
    top: int,
    size: int,
    max_width: int,
    bold: bool = False,
) -> None:
    text, size = _fitted(draw, text, size, max_width)
    stroke = 1 if bold else 0
    draw.text(
        (center_x, top),
        text,
        font=_text_font(size),
        fill=0,
        anchor="ma",
        stroke_width=stroke,
        stroke_fill=0,
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Band:
    text: str
    size: int  # font size in dots at the 30 mm (240-dot) reference height
    bold: bool = False
    drop_order: int = 0  # 0 = never dropped; higher numbers are dropped first when cramped


_HRI_SIZE = 17  # the human-readable barcode value under the bars


def _bands(kind: LabelKind, data: CardData) -> list[_Band]:
    if kind is LabelKind.ITEM_TAG:
        info = " · ".join(part for part in (data.subtitle, data.extra) if part)
        bands = [_Band(data.title, 26, bold=True)]
        if info:
            bands.append(_Band(info, 18, drop_order=2))
        return bands
    bands = [
        _Band("STOCKY · LIBRARY CARD", 15, drop_order=1),
        _Band(data.title, 30, bold=True),
    ]
    if data.subtitle:
        bands.append(_Band(data.subtitle, 18, drop_order=2))
    return bands


def _line_height(size: int) -> int:
    return size + 4


def _scaled(bands: list[_Band], geom: LabelGeometry) -> list[_Band]:
    factor = min(max(geom.height_dots / 240, 0.6), 1.6)
    return [replace(b, size=max(_MIN_TEXT, round(b.size * factor))) for b in bands]


def render(kind: LabelKind, geom: LabelGeometry, data: CardData) -> Image.Image:
    """Compose one label as a mode-"1" image sized to the geometry's full byte canvas.

    The canvas is `canvas_width_dots` wide (a byte multiple — BITMAP rows are whole bytes
    and padding bits print black), but everything is laid out within `print_width_dots`;
    the padding columns stay white.
    """
    bars_width = code128_width_dots(data.barcode)
    quiet = QUIET_MODULES * MODULE_DOTS
    if bars_width + 2 * quiet > geom.print_width_dots:
        needed_mm = (bars_width + 2 * quiet) / 8
        raise LabelTooNarrow(
            f"Barcode {data.barcode!r} needs {needed_mm:.1f} mm of printable width but the "
            f"{geom.width_mm:g} mm label gives {geom.print_width_dots / 8:.1f} mm. "
            "Use a shorter barcode or wider label stock."
        )

    image = Image.new("1", (geom.canvas_width_dots, geom.height_dots), 1)
    draw = ImageDraw.Draw(image)
    center_x = geom.print_width_dots // 2
    text_width = geom.print_width_dots - 2 * _SIDE_MARGIN

    bands = _scaled(_bands(kind, data), geom)
    factor = min(max(geom.height_dots / 240, 0.6), 1.6)
    hri_height = _line_height(max(_MIN_TEXT, round(_HRI_SIZE * factor)))

    def stack_height(bs: list[_Band]) -> int:
        return sum(_line_height(b.size) + _BAND_GAP for b in bs)

    # Drop the most expendable bands until the barcode gets at least its minimum height.
    available = geom.height_dots - 2 * _V_MARGIN
    while bands and stack_height(bands) + _BAR_MIN + _BAND_GAP + hri_height > available:
        droppable = [b for b in bands if b.drop_order > 0]
        if not droppable:
            break
        bands.remove(max(droppable, key=lambda b: b.drop_order))

    y = _V_MARGIN
    for band in bands:
        _draw_centered(
            draw,
            band.text,
            center_x=center_x,
            top=y,
            size=band.size,
            max_width=text_width,
            bold=band.bold,
        )
        y += _line_height(band.size) + _BAND_GAP

    # HRI pinned to the bottom; the bars fill (and center in) the space between.
    hri_top = geom.height_dots - _V_MARGIN - hri_height
    bar_space = hri_top - _BAND_GAP - y
    bar_height = min(max(bar_space, _BAR_MIN), _BAR_MAX)
    bar_y = y + max((bar_space - bar_height) // 2, 0)
    draw_code128(
        draw,
        data.barcode,
        x=center_x - bars_width // 2,
        y=bar_y,
        height_dots=bar_height,
    )
    _draw_centered(
        draw,
        data.barcode,
        center_x=center_x,
        top=hri_top,
        size=hri_height - 4,
        max_width=text_width,
    )
    return image


def render_png(kind: LabelKind, geom: LabelGeometry, data: CardData) -> bytes:
    """The exact printer raster as a PNG — the admin-UI preview is what the head prints."""
    buffer = BytesIO()
    render(kind, geom, data).save(buffer, format="PNG")
    return buffer.getvalue()


def render_mono_bytes(kind: LabelKind, geom: LabelGeometry, data: CardData) -> bytes:
    """The TSPL BITMAP payload (mode-"1" rows are already MSB-first with 0 = black)."""
    return render(kind, geom, data).tobytes()


def render_calibration(geom: LabelGeometry, *, density: int, gap_mm: float) -> Image.Image:
    """A device-diagnostic label: registration border, mm ruler, and the active config.

    Deliberately contains no domain data — its fixed content *is* the diagnostic (edge
    clipping shows registration/size problems, the ruler verifies 8 dots/mm, the text
    verifies density/darkness).
    """
    image = Image.new("1", (geom.canvas_width_dots, geom.height_dots), 1)
    draw = ImageDraw.Draw(image)
    width, height = geom.print_width_dots, geom.height_dots
    draw.rectangle([0, 0, width - 1, height - 1], outline=0, width=2)
    for x in range(0, width, 8):  # a tick every millimetre, taller every 5/10 mm
        tick = 14 if x % 80 == 0 else 10 if x % 40 == 0 else 6
        draw.rectangle([x, 2, x, 2 + tick], fill=0)
    center_x = width // 2
    text_width = width - 2 * _SIDE_MARGIN
    size_mm = f"{geom.width_mm:g} x {geom.height_mm:g} mm"
    config_line = f"{size_mm} · density {density} · gap {gap_mm:g} mm"
    lines = [
        ("Stocky label printer test", 22, True),
        (config_line, 16, False),
        (f"{width} x {height} dots @ 203 dpi", 16, False),
    ]
    y = 28
    for text, size, bold in lines:
        _draw_centered(
            draw, text, center_x=center_x, top=y, size=size, max_width=text_width, bold=bold
        )
        y += _line_height(size) + _BAND_GAP
    return image
