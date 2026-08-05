# Stocky

A simple, flexible **inventory-management app for classroom supplies**. Stocky helps teachers and
administrators track which students have borrowed which items, using barcode / ID-card scanning. It
is lightweight enough to run on a **Raspberry Pi 4**.

See [stocky.md](stocky.md) for the full product spec and [CLAUDE.md](CLAUDE.md) for the
engineering rules.

## Features

- **Administration** (admin-password protected) — five tabs: **Users & Groups** and **Inventory**
  (CRUD over nestable groups, item types, and items, with multi-select batch edits and `.xlsx`
  import/export), **History** (a filterable, paginated event log), **Export** (printable ID-card /
  item-tag PDFs), and **Settings**. Item availability (Checked out / Available / Unavailable / Lost
  / Discarded) is derived from the event log; physical condition and a "needs review" flag are
  tracked separately.
- **Check-in/out kiosk** — scan a student ID to log in, then scan items to check them in or out.
  Works directly with USB barcode scanners — no need to click into an input box first.
- **Inventory** — a read-only view for browsing items, locations, and quantities with search and
  filtering.

## Tech stack

| Layer    | Technology |
|----------|------------|
| Database | PostgreSQL 18 |
| Backend  | Python 3.13, FastAPI 0.138, SQLModel, Alembic (managed with **uv**) |
| Frontend | Next.js 16.2, Radix UI, TypeScript (managed with **npm**) |
| Ops      | Docker Compose + Makefile |

## Quick start

```bash
make init-env                 # generate .env with random secrets (prints the admin password)
make run                      # start postgres 18 + backend + frontend
make seed                     # load demo data (optional)
```

Then open:

- Admin:     http://localhost:3000/admin  (log in at `/login`)
- Kiosk:     http://localhost:3000/kiosk
- Inventory: http://localhost:3000/inventory
- API docs:  http://localhost:8000/docs

Run `make help` to see all available commands.

## Development

```bash
make install     # uv sync + npm install
make dev         # run backend (:8000) and frontend (:3000) locally
make test        # run all tests
make lint        # ruff + eslint
```

> **Note:** the backend is managed exclusively with `uv` — do not use `pip`. PostgreSQL is pinned
> to version 18 and must not be downgraded.
