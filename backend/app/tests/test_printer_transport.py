"""Transport tests against real OS device nodes (char device, pipe, pty) — no mocks.

The pty tests exercise the actual serial code path: `open_transport` auto-detects a tty
via isatty, applies raw-mode termios, and moves real bytes both directions with real
deadlines. A pty *is* a tty — the same kernel plumbing a /dev/rfcomm0 or /dev/cu.* node
uses above the driver.
"""

from __future__ import annotations

import os

import pytest

from app.services import tspl
from app.services.printer import PrinterUnavailable, _read_status
from app.services.printer_transport import TransportError, open_transport


def test_char_device_write_and_lock() -> None:
    # /dev/null is a real char device: exercises open, flock, chunked select()-write.
    with open_transport("/dev/null", "usb") as transport:
        assert transport.kind == "usb"
        transport.write(b"SIZE 50.0 mm,30.0 mm\r\n" + b"\x00" * 20000)  # > one chunk


def test_missing_device_raises() -> None:
    with pytest.raises(TransportError, match="Could not open"):
        with open_transport("/nonexistent/printer0", "usb"):
            pass


def test_exclusive_lock_blocks_second_opener(tmp_path) -> None:
    # flock semantics need a regular file or device; a temp file stands for the node.
    path = tmp_path / "printer"
    path.write_bytes(b"")
    with open_transport(str(path), "usb"):
        with pytest.raises(TransportError, match="in use"):
            with open_transport(str(path), "usb"):
                pass


def test_pty_auto_detects_serial_and_moves_bytes() -> None:
    controller, follower = os.openpty()
    try:
        with open_transport(os.ttyname(follower), "auto") as transport:
            assert transport.kind == "serial"
            transport.write(tspl.STATUS_QUERY)
            assert os.read(controller, 64) == tspl.STATUS_QUERY  # raw mode: bytes untouched

            frame = bytearray(16)
            frame[13] = 50
            crc = tspl.crc16_modbus(bytes(frame))
            os.write(controller, bytes(frame) + crc.to_bytes(2, "big"))
            status = tspl.parse_status(transport.read(tspl.STATUS_FRAME_LEN, timeout=2.0))
            assert status.ready and status.label_width_mm == 50
    finally:
        os.close(controller)
        os.close(follower)


def test_read_timeout_returns_partial() -> None:
    controller, follower = os.openpty()
    try:
        with open_transport(os.ttyname(follower), "serial") as transport:
            os.write(controller, b"\x01\x02")
            data = transport.read(18, timeout=0.3)  # only 2 bytes ever arrive
            assert data == b"\x01\x02"
    finally:
        os.close(controller)
        os.close(follower)


def test_short_status_read_maps_to_unavailable() -> None:
    controller, follower = os.openpty()
    try:
        with open_transport(os.ttyname(follower), "serial") as transport:
            os.write(controller, b"\x00" * 4)  # a truncated frame, then silence
            with pytest.raises(PrinterUnavailable, match="did not respond"):
                _read_status(transport)
    finally:
        os.close(controller)
        os.close(follower)


def test_drain_discards_stale_bytes() -> None:
    controller, follower = os.openpty()
    try:
        with open_transport(os.ttyname(follower), "serial") as transport:
            os.write(controller, b"stale bytes from an aborted job")
            transport.drain_input()
            assert transport.read(1, timeout=0.2) == b""
    finally:
        os.close(controller)
        os.close(follower)


def test_unsupported_baud_raises() -> None:
    controller, follower = os.openpty()
    try:
        with pytest.raises(TransportError, match="baud"):
            with open_transport(os.ttyname(follower), "serial", baud=12345):
                pass
    finally:
        os.close(controller)
        os.close(follower)
