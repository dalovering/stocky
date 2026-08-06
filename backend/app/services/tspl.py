"""TSPL2 command encoding and status-frame parsing for the Nelko PM220 label printer.

The PM220 (a rebadged Polono 2B-PM220) speaks a TSPL2 subset over a plain byte stream —
USB printer-class (`/dev/usb/lp0`) or Bluetooth SPP serial (`/dev/rfcomm0`, 115200 8N1 raw).
This module is the pure encoding layer: it builds command bytes and decodes status frames,
and never touches a device (see `services/printer_transport.py` for I/O).

Ground truth: the byte sequence below was captured from a real PM220 by the carny-labels
project and cross-checked against the pm220-macOS-driver CUPS filter and the Nelko P21
reverse-engineering notes. `test_tspl.py` freezes it byte-for-byte — do not "clean it up"
(e.g. the space in `GAP 6.0 mm, 0 mm` is verbatim from the working capture).

Firmware quirks that shape the design:
- The TSPL `BARCODE`/`QRCODE` commands are broken on this firmware family; barcodes must be
  rasterized by us and sent inside the `BITMAP` payload (see `services/label_raster.py`).
- There is no print-completion acknowledgement; the `\\x1b!o` status query (busy bit) is the
  only pacing signal available.
- 203 dpi, treated as exactly 8 dots/mm (TSPL convention); the print head covers 384 dots
  (48 mm), so a 50 mm label has ~1 mm unprintable at each edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

DOTS_PER_MM = 8  # TSPL convention for a 203 dpi head.
MAX_PRINT_WIDTH_DOTS = 384  # 48 mm print head.

# The status query. Doubles as the job preamble's first bytes (the confirmed-working capture
# opens every job with it), so a print job gets a fresh status frame to pre-flight against.
STATUS_QUERY = b"\x1b!o\r\n"
STATUS_FRAME_LEN = 18  # 16 status bytes + 2 CRC bytes.
BATTERY_QUERY = b"BATTERY?\r\n"


def mm_to_dots(value_mm: float) -> int:
    return round(value_mm * DOTS_PER_MM)


@dataclass(frozen=True)
class LabelGeometry:
    """A die-cut label size and its derived dot/byte dimensions.

    `canvas_width_dots` is `width_bytes * 8`, which may exceed `print_width_dots` when the
    dot width isn't a byte multiple. `BITMAP` rows are whole bytes and *padding bits print
    black on this firmware* (0 = black), so the rasterizer must render on the full canvas
    width and keep every column at x >= print_width_dots white.
    """

    width_mm: float
    height_mm: float

    @property
    def height_dots(self) -> int:
        return mm_to_dots(self.height_mm)

    @property
    def print_width_dots(self) -> int:
        return min(mm_to_dots(self.width_mm), MAX_PRINT_WIDTH_DOTS)

    @property
    def width_bytes(self) -> int:
        return ceil(self.print_width_dots / 8)

    @property
    def canvas_width_dots(self) -> int:
        return self.width_bytes * 8


def job_header(*, width_mm: float, height_mm: float, gap_mm: float, density: int) -> bytes:
    """The once-per-job preamble: status query + label geometry + darkness.

    `SIZE`/`GAP`/`DIRECTION`/`DENSITY` are persistent printer state, so they are sent once
    per job, not once per label. The leading `STATUS_QUERY` makes the printer emit an
    18-byte status frame — a live transport must read (and should pre-flight on) it.
    """
    return STATUS_QUERY + (
        f"SIZE {width_mm:.1f} mm,{height_mm:.1f} mm\r\n"
        f"GAP {gap_mm:.1f} mm, 0 mm\r\n"
        "DIRECTION 0,0\r\n"
        f"DENSITY {density}\r\n"
    ).encode("ascii")


def bitmap_command(data: bytes, *, width_bytes: int, height_dots: int, mode: int) -> bytes:
    """`BITMAP x,y,w,h,mode,<data>` — w in BYTES, h in dots, MSB first, bit 0 = black.

    Mode 1 (OR) is the documented TSPL mode and works on the PM220; mode 3 is a
    PM220-specific mode seen in the confirmed capture. Both are supported; the default
    lives in config (`printer_bitmap_mode`).
    """
    if len(data) != width_bytes * height_dots:
        raise ValueError(
            f"BITMAP payload is {len(data)} bytes; {width_bytes}x{height_dots} needs "
            f"{width_bytes * height_dots}."
        )
    return b"BITMAP 0,0,%d,%d,%d," % (width_bytes, height_dots, mode) + data + b"\r\n"


def label_block(data: bytes, *, width_bytes: int, height_dots: int, mode: int) -> bytes:
    """One label: clear the image buffer, load the bitmap, print one copy."""
    return (
        b"CLS\r\n"
        + bitmap_command(data, width_bytes=width_bytes, height_dots=height_dots, mode=mode)
        + b"PRINT 1\r\n"
    )


def encode_job(
    bitmaps: list[bytes],
    *,
    geometry: LabelGeometry,
    gap_mm: float,
    density: int,
    mode: int,
) -> bytes:
    """A complete, self-contained TSPL job for N labels.

    This is the exact stream a live transport writes (minus the interleaved status polls).
    It is also served as a downloadable `.tspl` job so the printer can be driven without
    the backend touching a device — e.g. `lp -o raw` through a raw CUPS queue on a Mac, or
    a future in-browser Web Serial / Web Bluetooth transport.
    """
    blocks = [
        label_block(
            data,
            width_bytes=geometry.width_bytes,
            height_dots=geometry.height_dots,
            mode=mode,
        )
        for data in bitmaps
    ]
    header = job_header(
        width_mm=geometry.width_mm,
        height_mm=geometry.height_mm,
        gap_mm=gap_mm,
        density=density,
    )
    return header + b"".join(blocks)


# ---------------------------------------------------------------------------
# Status frames
# ---------------------------------------------------------------------------


def crc16_modbus(data: bytes) -> int:
    """CRC-16/MODBUS: poly 0xA001 (reflected 0x8005), init 0xFFFF, no final xor."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class StatusFrameError(ValueError):
    """A status frame was truncated or failed its CRC check."""


# Byte 0 of the status frame is a flag byte.
_FLAG_LID_OPEN = 0x01
_FLAG_NO_PAPER = 0x04
_FLAG_BUSY = 0x20


@dataclass(frozen=True)
class PrinterStatus:
    """The decoded 16-byte status frame (`\\x1b!o` response).

    `label_*_mm` come from the roll's embedded RFID tag and are 0 when the tag is
    unreadable (e.g. third-party stock) — treat 0 as "unknown", not as a size.
    """

    raw: bytes
    flags: int
    label_length_mm: int  # byte 11
    label_width_mm: int  # byte 13

    @property
    def lid_open(self) -> bool:
        return bool(self.flags & _FLAG_LID_OPEN)

    @property
    def out_of_paper(self) -> bool:
        return bool(self.flags & _FLAG_NO_PAPER)

    @property
    def busy(self) -> bool:
        return bool(self.flags & _FLAG_BUSY)

    @property
    def ready(self) -> bool:
        return self.flags == 0


def parse_status(frame: bytes) -> PrinterStatus:
    """Decode and CRC-check an 18-byte status frame.

    The reverse-engineering notes describe the CRC trailer as big-endian, but MODBUS
    convention is little-endian and we have no capture that disambiguates — so both byte
    orders are accepted. That widens acceptance from 1/65536 to 2/65536 of corrupt frames,
    which is still a solid integrity check for a 5-cm cable.
    """
    if len(frame) < STATUS_FRAME_LEN:
        raise StatusFrameError(
            f"Status frame is {len(frame)} bytes, expected {STATUS_FRAME_LEN}: {frame.hex()!r}"
        )
    frame = frame[:STATUS_FRAME_LEN]
    body, trailer = frame[:16], frame[16:]
    crc = crc16_modbus(body)
    if trailer not in (crc.to_bytes(2, "big"), crc.to_bytes(2, "little")):
        raise StatusFrameError(
            f"Status frame CRC mismatch (calculated {crc:#06x}): {frame.hex()!r}"
        )
    return PrinterStatus(
        raw=frame,
        flags=body[0],
        label_length_mm=body[11],
        label_width_mm=body[13],
    )


def parse_battery(raw: bytes) -> int:
    """Decode the `BATTERY?` response: first byte is the charge percentage in BCD."""
    if not raw:
        raise StatusFrameError("Empty BATTERY? response.")
    return (raw[0] >> 4) * 10 + (raw[0] & 0x0F)
