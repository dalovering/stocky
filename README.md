# Stocky

A simple, flexible **inventory-management app for classroom supplies**. Stocky helps teachers and
administrators track which students have borrowed which items, using barcode / ID-card scanning. It
is lightweight enough to run on a **Raspberry Pi 4**.

See [stocky.md](stocky.md) for the full product spec and [CLAUDE.md](CLAUDE.md) for the
engineering rules.

## Features

- **Administration** (admin-password protected — set up in-app on first launch, changeable from
  Settings) — six tabs: **Users & Groups** and **Inventory**
  (CRUD over nestable groups, item types, and items, with multi-select batch edits and `.xlsx`
  import/export), **History** (a filterable, paginated event log, downloadable as `.xlsx` — for
  one user, one item, or everything), **Attendance** (per-group Present/Absent records for today,
  this week, or since each group's semester start; a day counts as scheduled when anyone in the
  group checked in), **Export** (printable ID-card / item-tag PDFs and a full-database `.xlsx` —
  every table as a sheet, never including the admin password), and **Settings**. Item availability (Checked out / Available / Unavailable / Lost
  / Discarded) is derived from the event log; physical condition and a "needs review" flag are
  tracked separately.
- **Check-in/out kiosk** — scan a student ID to log in, then scan items to check them in or out.
  Works directly with USB barcode scanners — no need to click into an input box first. A user's
  first scan of the day is also recorded as attendance in their history.
- **Inventory** — a read-only view for browsing items, locations, and quantities with search and
  filtering.
- **Label printing** (optional) — item tags and compact user badges print directly to a **Nelko
  PM220** thermal label printer (TSPL2 over USB or Bluetooth serial) from the same Users/Inventory
  print buttons, alongside the PDF downloads. See [Label printer](#label-printer-nelko-pm220).

## Tech stack

| Layer    | Technology |
|----------|------------|
| Database | PostgreSQL 18 |
| Backend  | Python 3.13, FastAPI 0.138, SQLModel, Alembic (managed with **uv**) |
| Frontend | Next.js 16.2, Radix UI, TypeScript (managed with **npm**) |
| Ops      | Docker Compose + Makefile |

## Quick start

```bash
make init-env                 # generate .env with random secrets
make run                      # start postgres 18 + backend + frontend
make seed                     # load demo data (optional)
```

Then open:

- Admin:     http://localhost:3000/admin  (first visit prompts you to set an admin password;
             log in at `/login` afterward)
- Kiosk:     http://localhost:3000/kiosk
- Inventory: http://localhost:3000/inventory
- API docs:  http://localhost:8000/docs

Run `make help` to see all available commands.

### Admin password

There is no admin password in `.env`. The first visit to `/admin` prompts you to create one, and it
is stored hashed (bcrypt) in the database. Change it from **Admin → Settings** — or, if you are
locked out and have terminal access on the host:

```bash
make reset-admin-pass         # prompts for a new admin password
```

Changing the password does not end sessions that are already signed in; rotate `JWT_SECRET` and
restart to do that.

**Admin → Settings** also holds the app's behavior knobs: the kiosk's inactivity auto-logout
(seconds), an admin idle auto-logout (minutes, enforced in the browser on top of the absolute
`JWT_EXPIRE_MINUTES` session limit), the app time zone (IANA name) used for attendance days
and spreadsheet export timestamps, and the label-printer card (enable switch, label stock size,
darkness, status check, test print).

### Label printer (Nelko PM220)

Stocky can print item tags and user badges straight to a Nelko PM220 (a TSPL2 thermal printer,
203 dpi, 48 mm max print width). Use **40 mm-wide or wider rolls** — a Stocky barcode needs 33 mm —
and Nelko/Marklife stock (third-party rolls often mis-feed). 50 × 30 mm is the default.

**Raspberry Pi over USB (recommended):**

1. Plug the printer in and power it on, then `make printer-probe` — you should see
   `/dev/usb/lp0` and an IEEE-1284 id mentioning `TSPL`. If CUPS is installed it steals the
   device: `sudo systemctl disable --now cups cups-browsed`.
2. On a fresh install, `make init-env` asks about the printer and writes all of this for
   you. For an existing `.env`, set `PRINTER_DEVICE=/dev/usb/lp0`, `PRINTER_GID` to the host
   `lp` gid (`getent group lp | cut -d: -f3`), and
   `COMPOSE_FILE=docker-compose.yml:docker-compose.printer.yml` (grants the backend container
   scoped access to `/dev/usb` — see that file for details).
3. `make build && make start`, then `make printer-status` and `make printer-test`.
4. In **Admin → Settings → Label printer**: check the status, print a test label, set the label
   size to the loaded roll, and flip **Enable label printing**. The print buttons on Users and
   Inventory now offer "Print to label printer" next to the PDF download.
5. `make printer-scan-check b=<item barcode>` prints a real tag — scan it at the kiosk to verify
   end to end.

If USB data turns out to be disabled on the unit, fall back to Bluetooth SPP: pair + `rfcomm bind`,
set `PRINTER_DEVICE=/dev/rfcomm0`, and swap the device mapping as described in
`docker-compose.printer.yml`.

**macOS (development, `make dev`):** macOS has no raw USB printer node, so pair the printer over
**Bluetooth** instead (System Settings → Bluetooth; it appears as a serial port). Then in `.env`
set `PRINTER_DEVICE=/dev/cu.<name>` (see `ls /dev/cu.*`) and use `make dev-printer-status` /
`make dev-printer-test`. Alternatively `python -m app.printer_cli job out.tspl` writes a raw job
you can send through a raw CUPS queue (`lp -o raw`) over USB.

The printer never blocks the rest of the app: with `PRINTER_DEVICE` unset or the setting disabled,
the UI is exactly the PDF-only app. Batches are capped at 50 labels per print.

### Updating

**Admin → Settings → Software update** shows the running version and the update targets published
on GitHub (the `main` branch, release tags, or a pasted commit hash) with the exact commands to
run. The app never updates itself — updates run from a terminal on the host:

```bash
make backup                   # always take a backup first
make update REF=main          # or REF=v0.2.0, or REF=<commit sha>
```

`make update` fetches, checks out the ref (branches fast-forward; tags/commits check out
detached), rebuilds the containers, and restarts the stack — pending DB migrations are applied
automatically on start. To roll back, run `make update REF=<previous ref>`; note migrations are
not automatically downgraded, so prefer rolling forward.

### Backup & restore

```bash
make backup                              # dump the DB to backups/stocky-<timestamp>.dump
make restore FILE=backups/stocky-....dump  # replace the DB with a dump (asks for confirmation)
```

Backups use `pg_dump` inside the Postgres container (compressed custom format), so nothing extra
needs to be installed on the host. Dumps contain real student names and land in the git-ignored
`backups/` directory — treat them like the private data they are. Take a backup before updating
or migrating, and note that `make restore` **replaces** everything added since the dump was taken.

## Development

```bash
make install     # uv sync + npm install
make dev         # run backend (:8000) and frontend (:3000) locally
make test        # run all tests
make lint        # ruff + eslint
```

> **Note:** the backend is managed exclusively with `uv` — do not use `pip`. PostgreSQL is pinned
> to version 18 and must not be downgraded.

## Deployment note

Stocky is built for a **trusted local network** — a Raspberry Pi on a school LAN. The kiosk and
read-only inventory endpoints are intentionally unauthenticated so students can scan without
logging in; only the administration surface requires a password. Don't port-forward it or put it
on a guest network. See [SECURITY.md](SECURITY.md) for the full threat model.

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the setup and
the handful of non-negotiable rules (Postgres 18, uv not pip, no fakes in tests, a migration with
every schema change).

Found a security problem? Please report it
[privately](https://github.com/dalovering/stocky/security/advisories/new) rather than opening an
issue.

## License

[MIT](LICENSE) © 2026 Dean Lovering
