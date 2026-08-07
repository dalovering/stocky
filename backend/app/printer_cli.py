"""Ops CLI for the label printer — drives the exact production service code.

Run inside the backend container (`make printer-status` / `printer-test` /
`printer-scan-check`) or in a `make dev` host environment (`make dev-printer-status`).
Going through `services/printer.py` rather than ad-hoc shell keeps the CLI and the API
on one code path — if the CLI prints, the app prints.

Commands:
    status          decode a live status frame + battery (no printing)
    test            print one calibration label (works with printing disabled)
    item BARCODE    print the real tag for an item, to scan back at the kiosk
    job FILE        write the calibration label as a raw TSPL job file, for transports
                    Stocky doesn't drive itself (macOS raw CUPS queue: lp -o raw FILE)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings as config
from app.core.db import async_session_maker
from app.models import Item
from app.schemas.printing import PrinterState
from app.schemas.settings import AppSettings
from app.services import cards as cards_svc
from app.services import label_raster as raster
from app.services import printer, tspl
from app.services import settings as settings_svc


async def _app_settings() -> AppSettings:
    async with async_session_maker() as session:
        return await settings_svc.load_settings(session)


def _print_outcome(outcome: printer.PrintOutcome) -> None:
    print(f"printed {outcome.printed}/{outcome.requested} ({outcome.bytes_sent} bytes sent)")
    for warning in outcome.warnings:
        print(f"warning: {warning}")


async def cmd_status() -> int:
    report = await printer.probe()
    state, message = printer.describe_probe(report)  # same interpretation as the admin API
    print(f"device:  {config.printer_device} (transport={config.printer_transport})")
    print(f"state:   {state} — {message}")
    status = report.status
    if status is not None:
        roll = f"{status.label_width_mm} x {status.label_length_mm} mm"
        print(
            f"roll:    {roll}"
            + ("  (0 = size tag unreadable)" if not status.label_width_mm else "")
        )
    if report.battery_percent is not None:
        print(f"battery: {report.battery_percent}%")
    # Connected (mute) still exits 0: the printer will print, it just can't be asked.
    return 0 if state in (PrinterState.READY, PrinterState.CONNECTED) else 1


async def cmd_test() -> int:
    _print_outcome(await printer.print_test_label(await _app_settings()))
    return 0


async def cmd_item(barcode: str) -> int:
    async with async_session_maker() as session:
        item = (
            await session.execute(select(Item).where(Item.barcode == barcode))
        ).scalar_one_or_none()
        if item is None:
            print(f"No item with barcode {barcode!r}.", file=sys.stderr)
            return 1
        cards = await cards_svc.build_item_cards(session, [item])
    _print_outcome(
        await printer.print_cards(raster.LabelKind.ITEM_TAG, cards, await _app_settings())
    )
    return 0


async def cmd_job(path: str) -> int:
    app_settings = await _app_settings()
    geometry = printer.geometry_from(app_settings)
    payload = raster.render_calibration(
        geometry, density=app_settings.label_density, gap_mm=app_settings.label_gap_mm
    ).tobytes()
    job = tspl.encode_job(
        [payload],
        geometry=geometry,
        gap_mm=app_settings.label_gap_mm,
        density=app_settings.label_density,
        mode=config.printer_bitmap_mode,
    )
    Path(path).write_bytes(job)
    print(f"wrote {len(job)} bytes to {path} — print raw, e.g.: lp -d <queue> -o raw {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="printer_cli", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("test")
    item = sub.add_parser("item")
    item.add_argument("barcode")
    job = sub.add_parser("job")
    job.add_argument("file")
    args = parser.parse_args(argv)

    try:
        match args.command:
            case "status":
                return asyncio.run(cmd_status())
            case "test":
                return asyncio.run(cmd_test())
            case "item":
                return asyncio.run(cmd_item(args.barcode))
            case "job":
                return asyncio.run(cmd_job(args.file))
    except printer.PrinterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except raster.LabelError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
