"""Render printable barcode label sheets (PDF) for users and inventory items.

Produces one PDF with two sections — a label per user and a label per item — each showing a
Code128 barcode (the same symbology the cheap USB kiosk scanners read) plus a human-readable
caption. ReportLab draws the barcodes as native vector graphics, so they stay crisp at any
print size, and emits a compact PDF that prints fine from a Raspberry Pi.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


@dataclass
class Label:
    """A single printable label: a barcode plus its captions."""

    title: str  # primary line — the person's or item's name
    subtitle: str | None  # secondary line — group or item-type name
    barcode: str  # the Code128 value the scanner reads


# Three labels per row fits comfortably on A4 with room for the barcode and captions.
COLUMNS = 3
PAGE_MARGIN = 12 * mm
BARCODE_HEIGHT = 12 * mm

_TITLE_STYLE = ParagraphStyle(
    "label-title", fontName="Helvetica-Bold", fontSize=9, leading=11, alignment=TA_CENTER
)
_SUBTITLE_STYLE = ParagraphStyle(
    "label-subtitle",
    fontName="Helvetica",
    fontSize=7,
    leading=9,
    alignment=TA_CENTER,
    textColor="#555555",
)
_CODE_STYLE = ParagraphStyle(
    "label-code",
    fontName="Helvetica",
    fontSize=7,
    leading=9,
    alignment=TA_CENTER,
    textColor="#555555",
)
_SECTION_STYLE = ParagraphStyle(
    "label-section", fontName="Helvetica-Bold", fontSize=15, leading=18, spaceAfter=6
)
_EMPTY_STYLE = ParagraphStyle(
    "label-empty", fontName="Helvetica-Oblique", fontSize=9, leading=12, textColor="#777777"
)


def _barcode_drawing(value: str, target_width: float) -> Flowable:
    """A Code128 barcode scaled to exactly `target_width` so every column lines up."""
    drawing = createBarcodeDrawing(
        "Code128", value=value, barHeight=BARCODE_HEIGHT, humanReadable=False
    )
    # Code128 width varies with the encoded length; rescale horizontally to the cell width.
    drawing.scale(target_width / drawing.width, 1)
    drawing.width = target_width
    return drawing


def _label_cell(label: Label, cell_width: float) -> list[Flowable]:
    """The stacked flowables for one label cell; a table row keeps them in one cell."""
    barcode_width = cell_width - 6 * mm
    parts: list[Flowable] = [Paragraph(escape(label.title), _TITLE_STYLE)]
    if label.subtitle:
        parts.append(Paragraph(escape(label.subtitle), _SUBTITLE_STYLE))
    parts.append(Spacer(1, 2 * mm))
    parts.append(_barcode_drawing(label.barcode, barcode_width))
    parts.append(Paragraph(escape(label.barcode), _CODE_STYLE))
    return parts


def _label_table(labels: list[Label], cell_width: float) -> Table:
    """Lay the labels out in a fixed-width grid."""
    cells = [_label_cell(label, cell_width) for label in labels]
    rows = []
    for start in range(0, len(cells), COLUMNS):
        row = cells[start : start + COLUMNS]
        row += [""] * (COLUMNS - len(row))  # pad the final row so the grid stays rectangular
        rows.append(row)
    table = Table(rows, colWidths=[cell_width] * COLUMNS)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _section(title: str, labels: list[Label], cell_width: float) -> list[Flowable]:
    story: list[Flowable] = [Paragraph(escape(title), _SECTION_STYLE)]
    if labels:
        story.append(_label_table(labels, cell_width))
    else:
        story.append(Paragraph(f"No {title.lower()} to print.", _EMPTY_STYLE))
    return story


def render_label_sheet(user_labels: list[Label], item_labels: list[Label]) -> bytes:
    """Build the two-section barcode-label PDF and return its bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="Stocky barcode labels",
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=PAGE_MARGIN,
    )
    cell_width = (doc.width) / COLUMNS
    story: list[Flowable] = []
    story += _section("Users", user_labels, cell_width)
    story.append(Spacer(1, 10 * mm))
    story += _section("Inventory", item_labels, cell_width)
    doc.build(story)
    return buffer.getvalue()
