"""Label rasterizer tests: geometry, module math, and a real decode-back of the bars.

The decode test walks the rendered pixel columns, checks every run is an exact multiple of
MODULE_DOTS (no fractional scaling crept in anywhere), then decodes the runs back through
the Code128 symbol table and verifies the mod-103 check symbol — a genuine scanner-style
read of the raster, no hardware needed.
"""

from __future__ import annotations

import pytest
from PIL import Image
from reportlab.graphics.barcode import code128

from app.services import label_raster as raster
from app.services.cards import CardData
from app.services.tspl import LabelGeometry

GEOM_50x30 = LabelGeometry(width_mm=50.0, height_mm=30.0)
ITEM = CardData(title="Stapler", subtitle="Office tools", extra="Shelf B", barcode="I0427193855")
USER = CardData(title="Alex Johnson", subtitle="Room 12", extra=None, barcode="U0427193855")


def test_module_math_for_stocky_code() -> None:
    # 11-char Stocky code -> 10 symbols incl. check + stop = 112 modules = 224 dots.
    pattern = raster.code128_pattern("I0427193855")
    assert sum(w for _, w in pattern) == 112
    assert raster.code128_width_dots("I0427193855") == 224
    assert pattern[0][0] is True and pattern[-1][0] is True  # starts and ends with a bar


def test_render_canvas_is_exact_bitmap_payload() -> None:
    image = raster.render(raster.LabelKind.ITEM_TAG, GEOM_50x30, ITEM)
    assert image.mode == "1"
    assert image.size == (GEOM_50x30.canvas_width_dots, GEOM_50x30.height_dots)
    payload = raster.render_mono_bytes(raster.LabelKind.ITEM_TAG, GEOM_50x30, ITEM)
    assert len(payload) == GEOM_50x30.width_bytes * GEOM_50x30.height_dots


def test_padding_columns_stay_white_on_fractional_width() -> None:
    # 37.1 mm -> 297 printable dots on a 304-dot canvas; columns 297..303 are BITMAP row
    # padding and must stay white (bit 0 = black would print a stripe down the label edge).
    geom = LabelGeometry(width_mm=37.1, height_mm=30.0)
    image = raster.render(raster.LabelKind.ITEM_TAG, geom, ITEM)
    pixels = image.load()
    for x in range(geom.print_width_dots, geom.canvas_width_dots):
        assert all(pixels[x, y] != 0 for y in range(geom.height_dots))


@pytest.mark.parametrize("kind", [raster.LabelKind.ITEM_TAG, raster.LabelKind.USER_BADGE])
def test_png_preview_renders(kind: raster.LabelKind) -> None:
    png = raster.render_png(kind, GEOM_50x30, ITEM if kind is raster.LabelKind.ITEM_TAG else USER)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_too_long_barcode_raises_not_degrades() -> None:
    data = CardData(title="X", subtitle=None, extra=None, barcode="ABCDEFGHIJKLMNOP")
    with pytest.raises(raster.LabelTooNarrow, match="mm"):
        raster.render(raster.LabelKind.ITEM_TAG, GEOM_50x30, data)


def test_stocky_code_needs_a_40mm_roll() -> None:
    # 224 bar dots + 2x20 quiet = 264 dots = 33 mm: fits 40 mm stock, not 30 mm stock.
    with pytest.raises(raster.LabelTooNarrow):
        raster.render(raster.LabelKind.ITEM_TAG, LabelGeometry(width_mm=30.0, height_mm=20.0), ITEM)
    raster.render(raster.LabelKind.ITEM_TAG, LabelGeometry(width_mm=40.0, height_mm=30.0), ITEM)


def test_calibration_label_renders_with_border() -> None:
    image = raster.render_calibration(GEOM_50x30, density=10, gap_mm=2.0)
    pixels = image.load()
    assert pixels[0, 0] == 0  # border corner is black
    assert pixels[GEOM_50x30.print_width_dots - 1, GEOM_50x30.height_dots - 1] == 0


# ---------------------------------------------------------------------------
# Decode-back: read the barcode out of the raster like a scanner would
# ---------------------------------------------------------------------------


def _barcode_runs(image: Image.Image) -> list[tuple[int, int]]:
    """(value, run_length) runs across the barcode band, quiet zones stripped."""
    pixels = image.load()
    width, height = image.size
    # The bars are the only place dozens of consecutive rows are pixel-identical (text rows
    # vary line to line): take the longest run of identical non-blank rows.
    rows = [tuple(0 if pixels[x, y] == 0 else 1 for x in range(width)) for y in range(height)]
    best_row, best_len, start = rows[0], 0, 0
    for y in range(1, height + 1):
        if y == height or rows[y] != rows[start]:
            if y - start > best_len and 0 in rows[start]:
                best_row, best_len = rows[start], y - start
            start = y
    row = list(best_row)
    runs: list[tuple[int, int]] = []
    for value in row:
        if runs and runs[-1][0] == value:
            runs[-1] = (value, runs[-1][1] + 1)
        else:
            runs.append((value, 1))
    # Strip leading/trailing white (quiet zones + margins).
    if runs and runs[0][0] == 1:
        runs = runs[1:]
    if runs and runs[-1][0] == 1:
        runs = runs[:-1]
    return runs


def _decode_code128(runs: list[tuple[int, int]]) -> str:
    """Decode module runs to text via the (public-spec) symbol table, verifying mod-103."""
    for _, length in runs:
        assert length % raster.MODULE_DOTS == 0, "bar/space width is not an integer module count"
    letters = ""
    for value, length in runs:
        modules = length // raster.MODULE_DOTS
        assert 1 <= modules <= 4
        letters += "ABCD"[modules - 1] if value == 0 else "abcd"[modules - 1]
    inverse = {pattern: symbol for symbol, pattern in code128._patterns.items()}
    chunks = [letters[:6]] + [letters[i : i + 6] for i in range(6, len(letters) - 7, 6)]
    symbols = [inverse[c] for c in chunks] + [inverse[letters[-7:]]]
    assert symbols[0] in (103, 104, 105), "missing start symbol"
    assert symbols[-1] == 106, "missing stop symbol"
    data, check = symbols[1:-2], symbols[-2]
    assert (symbols[0] + sum(i * s for i, s in enumerate(data, start=1))) % 103 == check
    # Decode set B / set C content (all Stocky codes start in set B).
    set_b = {value: char for char, value in code128.setb.items()}
    text, in_c = "", symbols[0] == 105
    for symbol in data:
        # 99/100 are only shift symbols in the *other* set: inside Code C, 99 is the
        # literal digit pair "99" (and in B, 100 is FNC4) — don't eat those as switches.
        if symbol == 99 and not in_c:
            in_c = True
        elif symbol == 100 and in_c:
            in_c = False
        elif in_c:
            text += f"{symbol:02d}"
        else:
            text += set_b[symbol]
    return text


@pytest.mark.parametrize(
    ("kind", "data"),
    [
        (raster.LabelKind.ITEM_TAG, ITEM),
        (raster.LabelKind.USER_BADGE, USER),
        # "99" pairs encode as Code C symbol 99, which doubles as the switch-to-C symbol
        # in set B — a decoder that confuses the two eats every such pair. Regression for
        # a flake that hit whenever the random allocator dealt a barcode containing 99.
        (
            raster.LabelKind.USER_BADGE,
            CardData(title="Ada", subtitle="Room 12", extra=None, barcode="U99999999"),
        ),
    ],
)
def test_rendered_barcode_decodes_back(kind: raster.LabelKind, data: CardData) -> None:
    image = raster.render(kind, GEOM_50x30, data)
    assert _decode_code128(_barcode_runs(image)) == data.barcode


def test_narrow_roll_barcode_decodes_back() -> None:
    image = raster.render(raster.LabelKind.ITEM_TAG, LabelGeometry(40.0, 30.0), ITEM)
    assert _decode_code128(_barcode_runs(image)) == ITEM.barcode


def test_long_names_shrink_or_ellipsize_without_error() -> None:
    data = CardData(
        title="An Extremely Long Item Name That Cannot Possibly Fit On A Small Label " * 2,
        subtitle="A very long item type name here",
        extra="Some distant storage location",
        barcode="I0427193855",
    )
    image = raster.render(raster.LabelKind.ITEM_TAG, GEOM_50x30, data)
    assert _decode_code128(_barcode_runs(image)) == data.barcode  # bars survive crowding
