"""Read models for the label-printer API."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PrinterState(StrEnum):
    """Display state for the admin UI (values are shown verbatim)."""

    NOT_CONFIGURED = "Not configured"
    NOT_CHECKED = "Not checked"  # configured, but this response didn't probe the device
    UNREACHABLE = "Unreachable"
    READY = "Ready"
    # Opened fine but answers no queries — normal for this printer family (the USB printer
    # interface can be unidirectional). It prints; we just can't check paper/lid first.
    CONNECTED = "Connected"
    NO_PAPER = "Out of paper"
    LID_OPEN = "Lid open"
    BUSY = "Busy"
    ERROR = "Error"


class PrinterInfo(BaseModel):
    """Printer configuration + (optionally probed) live state for the settings page."""

    configured: bool
    enabled: bool
    device: str | None
    transport: str
    state: PrinterState
    message: str = ""
    label_width_mm: float
    label_height_mm: float
    label_gap_mm: float
    label_density: int
    # From the roll's RFID tag when a probe reached the printer; None = unknown.
    roll_width_mm: int | None = None
    roll_length_mm: int | None = None
    battery_percent: int | None = None
    max_batch: int


class PrintResult(BaseModel):
    """Outcome of a print job; partial failures surface in `warnings`, never silently."""

    printed: int
    requested: int
    bytes_sent: int
    warnings: list[str] = Field(default_factory=list)
