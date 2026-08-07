"""Byte-stream transports for the label printer.

The PM220 is reached through an OS device node, in one of two flavors:

- **Printer-class char device** — Linux `usblp` (`/dev/usb/lp0`) when connected over USB.
- **Serial tty** — Bluetooth SPP (`/dev/rfcomm0` on Linux, `/dev/cu.<name>` on macOS) or a
  USB CDC node (`/dev/ttyACM*`). Ttys must be put into raw mode at 115200 8N1 or the line
  discipline mangles the TSPL stream (ONLCR rewrites the CRLF terminators, echo corrupts
  reads).

Both are byte streams, so one transport class serves both; the only difference is the
termios setup after open. `transport="auto"` picks by `os.isatty()`.

Robustness rules (stdlib only — no pyserial):
- The fd stays non-blocking and all I/O goes through `select()` with deadlines, so a
  powered-off or wedged printer can never hang a worker thread indefinitely.
- Jobs must end with `flush()`: with a non-blocking fd, write() returning only means the
  kernel queued the bytes, and usblp discards its in-flight URB on close — without the
  flush, the tail of the job (the PRINT command) silently never reaches the printer.
- An exclusive `flock` guards against a second *process* interleaving TSPL into the same
  job (the ops CLI, a future multi-worker uvicorn); in-process serialization is the
  printer service's asyncio lock. TSPL is stateful (CLS…PRINT), so interleaving two jobs
  corrupts both.
"""

from __future__ import annotations

import fcntl
import os
import select
import termios
import time
import tty
from collections.abc import Iterator
from contextlib import contextmanager

_WRITE_CHUNK = 4096  # keep writes small so pacing/status polls interleave predictably

_BAUD_CONSTANTS = {
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
    230400: termios.B230400,
}


class TransportError(Exception):
    """The device could not be opened, or I/O on it stalled or failed."""


class Transport:
    """A non-blocking byte-stream handle with deadline-bounded read/write."""

    def __init__(self, fd: int, path: str, kind: str) -> None:
        self._fd = fd
        self.path = path
        self.kind = kind  # "usb" (char device) or "serial" (tty)

    def write(self, data: bytes, *, timeout: float = 10.0) -> None:
        """Write everything, in chunks, waiting at most `timeout` for each chunk to drain."""
        view = memoryview(data)
        while view:
            chunk = view[:_WRITE_CHUNK]
            deadline = time.monotonic() + timeout
            while chunk:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TransportError(
                        f"Write to {self.path} stalled (printer buffer full or device gone)."
                    )
                _, writable, _ = select.select([], [self._fd], [], remaining)
                if not writable:
                    continue
                try:
                    written = os.write(self._fd, chunk)
                except BlockingIOError:
                    continue
                except OSError as exc:
                    raise TransportError(f"Write to {self.path} failed: {exc}") from exc
                chunk = chunk[written:]
            view = view[_WRITE_CHUNK:]

    def read(self, size: int, timeout: float) -> bytes:
        """Read up to `size` bytes, returning whatever arrived by the deadline."""
        deadline = time.monotonic() + timeout
        received = b""
        while len(received) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            readable, _, _ = select.select([self._fd], [], [], remaining)
            if not readable:
                continue
            try:
                chunk = os.read(self._fd, size - len(received))
            except BlockingIOError:
                continue
            except OSError as exc:
                raise TransportError(f"Read from {self.path} failed: {exc}") from exc
            if chunk == b"":  # EOF: the device vanished mid-read
                break
            received += chunk
        return received

    def flush(self, timeout: float = 5.0) -> None:
        """Wait (bounded) until everything written has actually left for the device.

        A non-blocking `os.write` returning means the kernel *accepted* the bytes, not
        that they reached the printer: usblp keeps the write in an in-flight URB, and
        close() unlinks it — silently discarding the tail of the job. (Observed on real
        hardware: a job "succeeded" but the final chunk with the PRINT command was
        dropped, so the printer did nothing.) usblp only reports writable once no URB is
        in flight, so waiting for one more writable edge proves delivery. Ttys don't
        discard on close (serial drivers drain, `closing_wait`), so the same bounded
        writability wait suffices there — deliberately not `tcdrain`, which has no
        deadline and can hang a worker thread forever (it deadlocks outright on the
        test ptys). Call this after the last write of a job, before the fd closes.
        """
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError(
                    f"Data written to {self.path} never finished sending "
                    "(device stalled or vanished)."
                )
            _, writable, _ = select.select([], [self._fd], [], remaining)
            if writable:
                return

    def drain_input(self) -> None:
        """Discard any stale bytes (e.g. an unread status frame from an aborted job)."""
        while True:
            readable, _, _ = select.select([self._fd], [], [], 0)
            if not readable:
                return
            try:
                if os.read(self._fd, 4096) == b"":
                    return
            except (BlockingIOError, OSError):
                return


def _configure_serial(fd: int, baud: int) -> None:
    speed = _BAUD_CONSTANTS.get(baud)
    if speed is None:
        raise TransportError(f"Unsupported baud rate {baud}.")
    tty.setraw(fd)
    attrs = termios.tcgetattr(fd)
    attrs[4] = attrs[5] = speed  # ispeed, ospeed
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


@contextmanager
def open_transport(path: str, kind: str = "auto", baud: int = 115200) -> Iterator[Transport]:
    """Open, lock, and configure the device; always closes on exit.

    Opened with O_NONBLOCK — also required at open() time for ttys, which otherwise block
    until carrier-detect (Bluetooth serial nodes never assert it).
    """
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError as exc:
        raise TransportError(f"Could not open the printer device at {path}: {exc}") from exc
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise TransportError(
                f"The printer device at {path} is in use by another process."
            ) from exc
        if kind == "auto":
            kind = "serial" if os.isatty(fd) else "usb"
        if kind == "serial":
            _configure_serial(fd, baud)
        yield Transport(fd, path, kind)
    finally:
        os.close(fd)
