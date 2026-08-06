"""Job-flow tests: drive `_run_job` through a real pty and capture what hits the wire.

This is a protocol-conformance harness, not a printer simulation: the far end of the pty
answers each `\\x1b!o` with a CRC-valid status frame (the same bytes real hardware sends)
so that OUR state machine — pre-flight ordering, per-label pacing, partial-failure
accounting — runs to completion and its exact output stream can be asserted on. No object
pretends to "be" a printer or to confirm that paper came out; the deliverable under test
is the byte stream and the control flow around it.
"""

from __future__ import annotations

import os
import select
import threading
import time

import pytest

from app.core.config import settings as app_config
from app.services import printer, tspl


def _frame(flags: int = 0, *, width_mm: int = 50, length_mm: int = 30) -> bytes:
    body = bytearray(16)
    body[0] = flags
    body[11] = length_mm
    body[13] = width_mm
    return bytes(body) + tspl.crc16_modbus(bytes(body)).to_bytes(2, "big")


class PtyResponder:
    """Reads the pty controller side; answers every status query with a canned frame."""

    def __init__(self, frames: list[bytes]) -> None:
        self.controller, self.follower = os.openpty()
        self.frames = frames  # consumed per query; the last frame repeats
        self.received = bytearray()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    @property
    def path(self) -> str:
        return os.ttyname(self.follower)

    def _pump(self) -> None:
        # select-with-timeout instead of a blocking read: a blocked os.read on a pty
        # can't be interrupted by close() on macOS, which deadlocks teardown.
        pending = b""
        while not self._stop.is_set():
            readable, _, _ = select.select([self.controller], [], [], 0.1)
            if not readable:
                continue
            try:
                chunk = os.read(self.controller, 65536)
            except OSError:
                return
            if not chunk:
                return
            self.received.extend(chunk)
            pending += chunk
            while tspl.STATUS_QUERY in pending:
                _, pending = pending.split(tspl.STATUS_QUERY, 1)
                frame = self.frames[0] if len(self.frames) == 1 else self.frames.pop(0)
                os.write(self.controller, frame)

    def wait_for(self, nbytes: int, timeout: float = 3.0) -> None:
        """Let the pump catch up with writes that raced past the caller's return."""
        deadline = time.monotonic() + timeout
        while len(self.received) < nbytes and time.monotonic() < deadline:
            time.sleep(0.02)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        os.close(self.controller)
        os.close(self.follower)


@pytest.fixture
def geometry() -> tspl.LabelGeometry:
    return tspl.LabelGeometry(width_mm=50.0, height_mm=30.0)


def _payload(geometry: tspl.LabelGeometry, fill: int) -> bytes:
    return bytes([fill]) * (geometry.width_bytes * geometry.height_dots)


def _with_device(monkeypatch, path: str) -> None:
    monkeypatch.setattr(app_config, "printer_device", path)
    monkeypatch.setattr(app_config, "printer_transport", "serial")


def test_job_stream_matches_encoder_output(monkeypatch, geometry) -> None:
    responder = PtyResponder([_frame(0)])
    try:
        _with_device(monkeypatch, responder.path)
        payloads = [_payload(geometry, 0xAA), _payload(geometry, 0x55)]
        outcome = printer._run_job(payloads, geometry, 2.0, 10, 50.0)
        assert (outcome.printed, outcome.requested) == (2, 2)
        assert outcome.warnings == []

        # The stream is the pure encoder's job plus the between-label status poll.
        expected = tspl.encode_job(payloads, geometry=geometry, gap_mm=2.0, density=10, mode=1)
        responder.wait_for(len(expected) + len(tspl.STATUS_QUERY))
        wire = bytes(responder.received)
        assert wire.replace(tspl.STATUS_QUERY, b"", 2) == expected.replace(
            tspl.STATUS_QUERY, b"", 1
        )
        assert outcome.bytes_sent == len(expected)
    finally:
        responder.close()


def test_preflight_rejects_no_paper_before_any_label(monkeypatch, geometry) -> None:
    responder = PtyResponder([_frame(0x04)])
    try:
        _with_device(monkeypatch, responder.path)
        with pytest.raises(printer.PrinterNotReady, match="out of paper"):
            printer._run_job([_payload(geometry, 0)], geometry, 2.0, 10, 50.0)
        assert b"BITMAP" not in bytes(responder.received)  # no paper moved
    finally:
        responder.close()


def test_preflight_rejects_roll_width_mismatch(monkeypatch, geometry) -> None:
    responder = PtyResponder([_frame(0, width_mm=40)])
    try:
        _with_device(monkeypatch, responder.path)
        with pytest.raises(printer.PrinterNotReady, match="40 mm wide.*50 mm"):
            printer._run_job([_payload(geometry, 0)], geometry, 2.0, 10, 50.0)
    finally:
        responder.close()


def test_unreadable_roll_tag_warns_but_prints(monkeypatch, geometry) -> None:
    responder = PtyResponder([_frame(0, width_mm=0, length_mm=0)])
    try:
        _with_device(monkeypatch, responder.path)
        outcome = printer._run_job([_payload(geometry, 0)], geometry, 2.0, 10, 50.0)
        assert outcome.printed == 1
        assert any("size tag" in w for w in outcome.warnings)
    finally:
        responder.close()


def test_paper_out_mid_batch_stops_with_warning(monkeypatch, geometry) -> None:
    # Ready for pre-flight, then "no paper" at the between-label poll after label 1.
    responder = PtyResponder([_frame(0), _frame(0x04)])
    try:
        _with_device(monkeypatch, responder.path)
        payloads = [_payload(geometry, n) for n in (1, 2, 3)]
        outcome = printer._run_job(payloads, geometry, 2.0, 10, 50.0)
        assert (outcome.printed, outcome.requested) == (1, 3)
        assert any("Paper ran out after 1 of 3" in w for w in outcome.warnings)
    finally:
        responder.close()


def test_silent_device_maps_to_unavailable(monkeypatch, geometry) -> None:
    controller, follower = os.openpty()  # nobody answers
    try:
        _with_device(monkeypatch, os.ttyname(follower))
        with pytest.raises(printer.PrinterUnavailable, match="did not respond"):
            printer._run_job([_payload(geometry, 0)], geometry, 2.0, 10, 50.0)
    finally:
        os.close(controller)
        os.close(follower)


@pytest.mark.asyncio
async def test_print_cards_gates(monkeypatch) -> None:
    from app.schemas.settings import AppSettings
    from app.services.cards import CardData
    from app.services.label_raster import LabelKind

    card = CardData(title="X", subtitle=None, extra=None, barcode="I0000000001")

    monkeypatch.setattr(app_config, "printer_device", "")
    with pytest.raises(printer.PrinterNotReady, match="turned off"):
        await printer.print_cards(LabelKind.ITEM_TAG, [card], AppSettings())
    with pytest.raises(printer.PrinterNotConfigured, match="not configured"):
        await printer.print_cards(LabelKind.ITEM_TAG, [card], AppSettings(printer_enabled=True))

    monkeypatch.setattr(app_config, "printer_device", "/dev/null")
    too_many = [card] * (printer.MAX_BATCH_LABELS + 1)
    with pytest.raises(printer.PrinterNotReady, match="at most 50"):
        await printer.print_cards(LabelKind.ITEM_TAG, too_many, AppSettings(printer_enabled=True))
