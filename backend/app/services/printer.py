"""Print-job orchestration for the label printer.

Flow of a job (all hardware-verified sequences live in `services/tspl.py`):

1. Open + exclusively lock the device (`printer_transport`).
2. Write the job header — its leading `\\x1b!o` makes the printer answer with a status
   frame in the same round trip. Decode it and **pre-flight**: no paper, open lid, or a
   roll that contradicts the configured label width rejects the job before any paper
   moves. The roll check reads the width the roll's RFID tag reports (0 = unreadable
   third-party stock -> trust the setting, warn).
3. Per label: `CLS` + `BITMAP` + `PRINT 1`. Between labels, poll the busy bit — the
   firmware has no completion ack and a bounded input buffer, so this is both flow
   control and the partial-failure story (paper out at label 17/30 stops with a warning
   instead of silently dropping 13 labels). Every poll loop is deadline-capped; nothing
   here can wait forever.

Concurrency: `_job_lock` serializes jobs in this process; the transport's flock covers
other processes (the ops CLI). The compose `command:` runs a single uvicorn worker —
adding `--workers N` would be safe against corruption (flock) but jobs would 503 instead
of queueing; keep one worker.

Batches are capped at MAX_BATCH_LABELS: a 200-label run is minutes of a held POST, which
browsers and proxies kill. A print-queue feature is the honest fix if it's ever needed.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from functools import partial

import anyio.to_thread

from app.core.config import settings
from app.schemas.settings import AppSettings
from app.services import label_raster as raster
from app.services import tspl
from app.services.cards import CardData
from app.services.printer_transport import Transport, TransportError, open_transport
from app.services.tspl import LabelGeometry

MAX_BATCH_LABELS = 50
_STATUS_TIMEOUT = 1.5  # seconds to wait for an 18-byte status frame
_BUSY_POLL_CAP = 8.0  # per-label ceiling on waiting for the busy bit to clear
_POLL_INTERVAL = 0.25
_WAKE_ATTEMPTS = 3  # ESC!o is cancel-pause; the vendor app repeats it, so so do we
_FEED_MM_PER_S = 60.0  # rated feed speed, used to pace batches on a printer with no status

MUTE_WARNING = (
    "This printer does not report its status, so Stocky cannot check for paper or a "
    "closed lid before printing."
)


class PrinterError(Exception):
    """Base for printer failures; routers map subclasses to HTTP statuses."""


class PrinterNotConfigured(PrinterError):
    """No PRINTER_DEVICE is set (409)."""


class PrinterUnavailable(PrinterError):
    """The device can't be opened or doesn't respond (503)."""


class PrinterNotReady(PrinterError):
    """The printer answered but can't print: lid, paper, roll mismatch, batch cap (409)."""


@dataclass(frozen=True)
class PrintOutcome:
    printed: int
    requested: int
    bytes_sent: int
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProbeReport:
    """What a live status probe found; `error` is set when the device was unreachable."""

    status: tspl.PrinterStatus | None
    battery_percent: int | None
    error: str | None


_job_lock = asyncio.Lock()


def _device() -> str:
    if not settings.printer_device:
        raise PrinterNotConfigured("The label printer is not configured.")
    return settings.printer_device


def geometry_from(app_settings: AppSettings) -> LabelGeometry:
    return LabelGeometry(
        width_mm=app_settings.label_width_mm, height_mm=app_settings.label_height_mm
    )


# ---------------------------------------------------------------------------
# Sync core — runs in a worker thread; must never block unboundedly
# ---------------------------------------------------------------------------


def _read_status(transport: Transport) -> tspl.PrinterStatus:
    raw = transport.read(tspl.STATUS_FRAME_LEN, _STATUS_TIMEOUT)
    if len(raw) < tspl.STATUS_FRAME_LEN:
        raise PrinterUnavailable(
            "The label printer did not respond. Check that it is powered on and connected."
        )
    try:
        return tspl.parse_status(raw)
    except tspl.StatusFrameError as exc:
        raise PrinterUnavailable(f"The label printer sent a garbled status frame: {exc}") from exc


def read_status_optional(transport: Transport) -> tspl.PrinterStatus | None:
    """The status frame, or None if this printer has no usable status channel.

    Many units in this family never answer queries: the USB printer interface can be
    *unidirectional* (`bInterfaceProtocol=1`), which makes a read path physically
    impossible, and the Bluetooth SPP channel can be equally mute. Printing works fine on
    such a printer, so silence must never block a job — it only costs us the pre-flight
    checks. Verified on real hardware: a PM220 that prints correctly answers neither
    `ESC !o` nor `CONFIG?` on either transport.
    """
    try:
        return _read_status(transport)
    except PrinterUnavailable:
        return None


def _query_status(transport: Transport) -> tspl.PrinterStatus | None:
    """Send the wake/cancel-pause command and read the status it may return.

    `ESC !o` is TSPL's cancel-pause, which this firmware family answers with a short
    status; the vendor app sends it repeatedly, so we retry a few times before concluding
    the printer is mute.
    """
    transport.drain_input()
    for _ in range(_WAKE_ATTEMPTS):
        transport.write(tspl.STATUS_QUERY)
        status = read_status_optional(transport)
        if status is not None:
            return status
    return None


def _preflight(status: tspl.PrinterStatus, expected_width_mm: float) -> list[str]:
    """Reject a doomed job before any paper moves; returns non-fatal warnings."""
    if status.out_of_paper:
        raise PrinterNotReady("The label printer is out of paper.")
    if status.lid_open:
        raise PrinterNotReady("The label printer's lid is open.")
    if status.busy:
        raise PrinterNotReady("The label printer is busy.")
    if status.flags != 0:
        raise PrinterNotReady(f"The label printer reported an error (status 0x{status.flags:02x}).")
    if status.label_width_mm == 0:
        return ["The roll's size tag could not be read; trusting the configured label size."]
    if abs(status.label_width_mm - expected_width_mm) > 1:
        raise PrinterNotReady(
            f"The loaded roll is {status.label_width_mm} mm wide but Stocky is set to "
            f"{expected_width_mm:g} mm labels. Update the label size in Settings."
        )
    return []


def _pace_blind(height_mm: float) -> None:
    """Wait out one label's travel when there's no status channel to poll.

    With neither a completion ack nor a readable busy bit, the only flow control left is
    the clock: hold off roughly as long as the label takes to feed at the rated speed, so
    a long batch can't outrun the printer's input buffer.
    """
    time.sleep(min(height_mm / _FEED_MM_PER_S + 0.3, 3.0))


def _wait_between_labels(transport: Transport, warnings: list[str]) -> bool:
    """Poll until the printer is no longer busy; False = stop the batch (paper out).

    The busy-bit timing is only partly documented, so this loop is deliberately
    forgiving: unparseable or missing frames are retried until the cap, then we continue
    optimistically rather than abort a batch the printer may be handling fine.
    """
    deadline = time.monotonic() + _BUSY_POLL_CAP
    while time.monotonic() < deadline:
        status = _query_status(transport)
        if status is None:
            time.sleep(_POLL_INTERVAL)
            continue
        if status.out_of_paper:
            return False
        if not status.busy:
            return True
        time.sleep(_POLL_INTERVAL)
    warnings.append(f"The printer was still busy after {_BUSY_POLL_CAP:g}s; continuing to send.")
    return True


def _run_job(
    payloads: list[bytes],
    geometry: LabelGeometry,
    gap_mm: float,
    density: int,
    expected_width_mm: float,
) -> PrintOutcome:
    header = tspl.job_header(
        width_mm=geometry.width_mm,
        height_mm=geometry.height_mm,
        gap_mm=gap_mm,
        density=density,
    )
    mode = settings.printer_bitmap_mode
    try:
        with open_transport(
            _device(), settings.printer_transport, settings.printer_baud
        ) as transport:
            transport.drain_input()
            transport.write(header)
            # The header's leading ESC!o may or may not be answered; a mute printer still
            # prints, so silence costs us the pre-flight checks and nothing else.
            status = read_status_optional(transport)
            if status is None:
                mute, warnings = True, [MUTE_WARNING]
            else:
                mute, warnings = False, _preflight(status, expected_width_mm)
            bytes_sent = len(header)
            printed = 0
            for index, payload in enumerate(payloads):
                block = tspl.label_block(
                    payload,
                    width_bytes=geometry.width_bytes,
                    height_dots=geometry.height_dots,
                    mode=mode,
                )
                transport.write(block)
                bytes_sent += len(block)
                printed += 1
                if index == len(payloads) - 1:
                    continue
                if mute:
                    _pace_blind(geometry.height_mm)
                elif not _wait_between_labels(transport, warnings):
                    warnings.append(f"Paper ran out after {printed} of {len(payloads)} labels.")
                    break
            return PrintOutcome(printed, len(payloads), bytes_sent, warnings)
    except TransportError as exc:
        raise PrinterUnavailable(str(exc)) from exc


def _run_probe() -> ProbeReport:
    try:
        with open_transport(
            _device(), settings.printer_transport, settings.printer_baud
        ) as transport:
            status = _query_status(transport)
            battery = _query_battery(transport) if status is not None else None
            return ProbeReport(status=status, battery_percent=battery, error=None)
    except TransportError as exc:
        return ProbeReport(status=None, battery_percent=None, error=str(exc))
    except PrinterUnavailable as exc:
        return ProbeReport(status=None, battery_percent=None, error=str(exc))


def _query_battery(transport: Transport) -> int | None:
    """Best-effort battery read; ASCII queries may echo before responding."""
    try:
        transport.drain_input()
        transport.write(tspl.BATTERY_QUERY)
        raw = transport.read(len(tspl.BATTERY_QUERY) + 2, 0.8)
        if raw.startswith(tspl.BATTERY_QUERY):
            raw = raw[len(tspl.BATTERY_QUERY) :]
        return tspl.parse_battery(raw) if raw else None
    except (TransportError, tspl.StatusFrameError):
        return None


# ---------------------------------------------------------------------------
# Async surface used by the API and the ops CLI
# ---------------------------------------------------------------------------


def _render_payloads(
    kind: raster.LabelKind, cards: list[CardData], geometry: LabelGeometry
) -> list[bytes]:
    return [raster.render_mono_bytes(kind, geometry, card) for card in cards]


async def print_cards(
    kind: raster.LabelKind, cards: list[CardData], app_settings: AppSettings
) -> PrintOutcome:
    """Render and print one label per card. Raises before any I/O on a doomed batch."""
    if not app_settings.printer_enabled:
        raise PrinterNotReady("Label printing is turned off in Settings.")
    _device()  # fail fast with 409 before rendering anything
    if len(cards) > MAX_BATCH_LABELS:
        raise PrinterNotReady(
            f"You selected {len(cards)} labels; print at most {MAX_BATCH_LABELS} at a time."
        )
    if not cards:
        return PrintOutcome(0, 0, 0, [])
    geometry = geometry_from(app_settings)
    payloads = _render_payloads(kind, cards, geometry)  # LabelError propagates (409)
    async with _job_lock:
        return await anyio.to_thread.run_sync(
            partial(
                _run_job,
                payloads,
                geometry,
                app_settings.label_gap_mm,
                app_settings.label_density,
                app_settings.label_width_mm,
            )
        )


async def print_test_label(app_settings: AppSettings) -> PrintOutcome:
    """One calibration label. Works with printing disabled — it's the setup diagnostic."""
    _device()
    geometry = geometry_from(app_settings)
    image = raster.render_calibration(
        geometry, density=app_settings.label_density, gap_mm=app_settings.label_gap_mm
    )
    async with _job_lock:
        return await anyio.to_thread.run_sync(
            partial(
                _run_job,
                [image.tobytes()],
                geometry,
                app_settings.label_gap_mm,
                app_settings.label_density,
                app_settings.label_width_mm,
            )
        )


async def probe() -> ProbeReport:
    """A live status + battery read; never raises for an unreachable device."""
    _device()
    async with _job_lock:
        return await anyio.to_thread.run_sync(_run_probe)


def encode_cards_job(
    kind: raster.LabelKind, cards: list[CardData], app_settings: AppSettings
) -> bytes:
    """The complete TSPL job as bytes, for transports Stocky doesn't drive itself.

    This is the seam for printing without backend device access: download and pipe to a
    raw queue (`lp -o raw`), or — future — fetch from the browser and write over Web
    Serial / Web Bluetooth. Pure function; no device, no printer_enabled gate.
    """
    geometry = geometry_from(app_settings)
    return tspl.encode_job(
        _render_payloads(kind, cards, geometry),
        geometry=geometry,
        gap_mm=app_settings.label_gap_mm,
        density=app_settings.label_density,
        mode=settings.printer_bitmap_mode,
    )
