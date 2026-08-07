"""TSPL2 encoder and status-frame tests.

The job-header and BITMAP equality tests freeze the byte sequence that was captured from a
real PM220 (carny-labels, 40x30 mm stock) — the only hardware-verified ground truth we
have. If one of these fails after a refactor, the refactor is wrong, not the test.
"""

from __future__ import annotations

import pytest

from app.services import tspl


def test_crc16_modbus_known_vector() -> None:
    # The standard CRC-16/MODBUS check value for b"123456789".
    assert tspl.crc16_modbus(b"123456789") == 0x4B37


def test_job_header_matches_hardware_capture() -> None:
    assert tspl.job_header(width_mm=40.0, height_mm=30.0, gap_mm=6.0, density=10) == (
        b"\x1b!o\r\nSIZE 40.0 mm,30.0 mm\r\nGAP 6.0 mm, 0 mm\r\nDIRECTION 0,0\r\nDENSITY 10\r\n"
    )


def test_bitmap_command_matches_hardware_capture() -> None:
    data = b"\x00" * 9600  # 40 bytes x 240 rows, all black (bit 0 = black).
    assert tspl.bitmap_command(data, width_bytes=40, height_dots=240, mode=3) == (
        b"BITMAP 0,0,40,240,3," + data + b"\r\n"
    )


def test_bitmap_command_rejects_wrong_payload_size() -> None:
    with pytest.raises(ValueError, match="9600"):
        tspl.bitmap_command(b"\x00" * 100, width_bytes=40, height_dots=240, mode=1)


def test_label_block_shape() -> None:
    data = b"\xff" * (48 * 240)
    block = tspl.label_block(data, width_bytes=48, height_dots=240, mode=1)
    assert block.startswith(b"CLS\r\nBITMAP 0,0,48,240,1,")
    assert block.endswith(b"PRINT 1\r\n")


def test_encode_job_concatenates_header_and_blocks() -> None:
    geom = tspl.LabelGeometry(width_mm=50.0, height_mm=30.0)
    bitmaps = [b"\xff" * (geom.width_bytes * geom.height_dots) for _ in range(3)]
    job = tspl.encode_job(bitmaps, geometry=geom, gap_mm=2.0, density=10, mode=1)
    assert job.startswith(tspl.STATUS_QUERY + b"SIZE 50.0 mm,30.0 mm\r\n")
    assert job.count(b"CLS\r\n") == 3
    assert job.count(b"PRINT 1\r\n") == 3


class TestLabelGeometry:
    def test_50x30_caps_at_head_width(self) -> None:
        # 50 mm = 400 dots, but the head prints 384; 384 is an exact byte multiple.
        geom = tspl.LabelGeometry(width_mm=50.0, height_mm=30.0)
        assert geom.print_width_dots == 384
        assert geom.width_bytes == 48
        assert geom.canvas_width_dots == 384
        assert geom.height_dots == 240

    def test_40x30(self) -> None:
        geom = tspl.LabelGeometry(width_mm=40.0, height_mm=30.0)
        assert (geom.print_width_dots, geom.width_bytes, geom.canvas_width_dots) == (320, 40, 320)

    def test_fractional_width_pads_to_byte_multiple(self) -> None:
        # 37.1 mm -> 297 dots -> 38 bytes -> a 304-dot canvas with 7 padding columns.
        geom = tspl.LabelGeometry(width_mm=37.1, height_mm=25.9)
        assert geom.print_width_dots == 297
        assert geom.width_bytes == 38
        assert geom.canvas_width_dots == 304


def _frame(flags: int = 0, *, length_mm: int = 30, width_mm: int = 50, order: str = "big") -> bytes:
    body = bytearray(16)
    body[0] = flags
    body[11] = length_mm
    body[13] = width_mm
    crc = tspl.crc16_modbus(bytes(body))
    return bytes(body) + crc.to_bytes(2, order)  # type: ignore[arg-type]


class TestParseStatus:
    def test_ready_frame_with_roll_dimensions(self) -> None:
        status = tspl.parse_status(_frame(0))
        assert status.ready
        assert not (status.lid_open or status.out_of_paper or status.busy)
        assert status.label_length_mm == 30
        assert status.label_width_mm == 50

    @pytest.mark.parametrize(
        ("flags", "attr"),
        [(0x01, "lid_open"), (0x04, "out_of_paper"), (0x20, "busy")],
    )
    def test_flag_bits(self, flags: int, attr: str) -> None:
        status = tspl.parse_status(_frame(flags))
        assert getattr(status, attr)
        assert not status.ready

    def test_combined_flags(self) -> None:
        status = tspl.parse_status(_frame(0x05))
        assert status.lid_open and status.out_of_paper

    @pytest.mark.parametrize("order", ["big", "little"])
    def test_both_crc_byte_orders_accepted(self, order: str) -> None:
        assert tspl.parse_status(_frame(0, order=order)).ready

    def test_corrupt_crc_raises(self) -> None:
        frame = bytearray(_frame(0))
        frame[16] ^= 0xFF
        frame[17] ^= 0xFF
        with pytest.raises(tspl.StatusFrameError, match="CRC"):
            tspl.parse_status(bytes(frame))

    def test_truncated_frame_raises(self) -> None:
        with pytest.raises(tspl.StatusFrameError, match="expected 18"):
            tspl.parse_status(b"\x00" * 5)


def test_parse_battery_bcd() -> None:
    assert tspl.parse_battery(b"\x87\x00") == 87
    assert tspl.parse_battery(b"\x05") == 5
    with pytest.raises(tspl.StatusFrameError):
        tspl.parse_battery(b"")
