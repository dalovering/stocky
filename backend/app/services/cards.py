"""Render printable item tags and user ID cards from SVG templates.

Each card is an SVG template (app/templates/) with `{{placeholder}}` text tokens and a
`rect#barcode-slot` marking where the Code128 barcode goes. We fill the text, render the static
artwork to a ReportLab drawing via svglib, and overlay a crisp vector barcode (ReportLab's own
Code128) into the slot — svglib draws the frame/text, ReportLab draws the bars. Pure-Python so it
runs fine on a Raspberry Pi.

Three layouts: a single card on a card-sized page, one card per page (a whole group/type), and a
multi-up troubleshooting sheet on US Letter with an ID-card section and an item-tag section.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg

_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


@dataclass(frozen=True)
class CardSpec:
    template: str
    width: float  # points
    height: float


ITEM_TAG = CardSpec("item_tag.svg", 1.46 * inch, 1.02 * inch)
ID_CARD = CardSpec("user_id_card.svg", 3.375 * inch, 2.125 * inch)


@dataclass
class CardData:
    title: str
    subtitle: str | None
    extra: str | None
    barcode: str


def _fill_template(spec: CardSpec, data: CardData) -> str:
    text = (_TEMPLATES / spec.template).read_text(encoding="utf-8")
    tokens = {
        "title": data.title,
        "subtitle": data.subtitle or "",
        "extra": data.extra or "",
        "barcode": data.barcode,
    }
    for key, value in tokens.items():
        text = text.replace("{{" + key + "}}", escape(str(value)))
    return text


def _barcode_slot(svg_text: str) -> tuple[float, float, float, float]:
    """The (x, y, width, height) of rect#barcode-slot in the template's (top-down) coordinates."""
    root = ET.fromstring(svg_text)
    for element in root.iter():
        if element.get("id") == "barcode-slot":
            return (
                float(element.get("x", 0)),
                float(element.get("y", 0)),
                float(element.get("width", 0)),
                float(element.get("height", 0)),
            )
    raise ValueError(f"Template {svg_text[:40]!r} has no rect#barcode-slot.")


def _barcode_drawing(value: str, width: float, height: float) -> Drawing:
    drawing = createBarcodeDrawing("Code128", value=value, barHeight=height, humanReadable=False)
    # Code128 width depends on the encoded length; rescale horizontally to the slot width.
    drawing.scale(width / drawing.width, 1)
    drawing.width = width
    return drawing


def _draw_card(c: canvas.Canvas, spec: CardSpec, data: CardData, ox: float, oy: float) -> None:
    """Draw one card with its bottom-left corner at (ox, oy) on the canvas."""
    svg_text = _fill_template(spec, data)
    drawing = svg2rlg(BytesIO(svg_text.encode("utf-8")))
    # svglib renders at 96dpi (0.75x of points); normalize the drawing to the exact card size so
    # the template's viewBox units map 1:1 to points and line up with the barcode overlay.
    drawing.scale(spec.width / drawing.width, spec.height / drawing.height)
    drawing.width, drawing.height = spec.width, spec.height
    renderPDF.draw(drawing, c, ox, oy)

    sx, sy, sw, sh = _barcode_slot(svg_text)
    barcode = _barcode_drawing(data.barcode, sw, sh)
    # SVG y is top-down; convert the slot's top-left to the barcode's bottom-left on the canvas.
    barcode.drawOn(c, ox + sx, oy + spec.height - sy - sh)


def render_single(spec: CardSpec, data: CardData) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(spec.width, spec.height))
    _draw_card(c, spec, data, 0, 0)
    c.showPage()
    c.save()
    return buffer.getvalue()


def render_per_page(spec: CardSpec, cards: list[CardData]) -> bytes:
    """One card per page (e.g. every item in a type, or every user in a group)."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(spec.width, spec.height))
    if not cards:
        c.setFont("Helvetica", 10)
        c.drawCentredString(spec.width / 2, spec.height / 2, "Nothing to print.")
        c.showPage()
    for data in cards:
        _draw_card(c, spec, data, 0, 0)
        c.showPage()
    c.save()
    return buffer.getvalue()


def render_multi_up(id_cards: list[CardData], item_tags: list[CardData]) -> bytes:
    """A US-Letter sheet with an ID-card section and an item-tag section (troubleshooting)."""
    buffer = BytesIO()
    width, height = letter
    c = canvas.Canvas(buffer, pagesize=letter)
    margin, gap = 36.0, 12.0
    y = height - margin

    def new_page() -> None:
        nonlocal y
        c.showPage()
        y = height - margin

    def section(title: str, spec: CardSpec, cards: list[CardData]) -> None:
        nonlocal y
        if not cards:
            return
        if y - 18 < margin:
            new_page()
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, y - 13, title)
        y -= 26
        cols = max(1, int((width - 2 * margin + gap) // (spec.width + gap)))
        for start in range(0, len(cards), cols):
            if y - spec.height < margin:
                new_page()
            for column, data in enumerate(cards[start : start + cols]):
                ox = margin + column * (spec.width + gap)
                _draw_card(c, spec, data, ox, y - spec.height)
            y -= spec.height + gap

    section("ID cards", ID_CARD, id_cards)
    if id_cards and item_tags:
        y -= gap
    section("Item tags", ITEM_TAG, item_tags)
    if not id_cards and not item_tags:
        c.setFont("Helvetica", 11)
        c.drawString(margin, height - margin - 20, "Nothing to print.")
    c.showPage()
    c.save()
    return buffer.getvalue()
