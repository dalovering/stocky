# Stocky

A simple, flexible **inventory-management app for classroom supplies**. Stocky helps teachers and
administrators track which students have borrowed which items, using barcode / ID-card scanning. It
is lightweight enough to run on a **Raspberry Pi 4**.

See [stocky.md](stocky.md) for the full product spec and [CLAUDE.md](CLAUDE.md) for the
engineering rules.

## Features

- **Administration** (admin-password protected — set up in-app on first launch, changeable from
  Settings) — five tabs: **Users & Groups** and **Inventory**
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
