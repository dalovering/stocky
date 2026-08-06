# Stocky backend — guide for Claude

FastAPI + SQLModel API over PostgreSQL 18. Read the root [../CLAUDE.md](../CLAUDE.md) first;
its golden rules apply here. This file covers backend-specific conventions.

## Tooling — uv only

- **Never use pip.** Manage everything through `uv`:
  - `uv add <pkg>` / `uv add --dev <pkg>` — add a dependency (updates `pyproject.toml` + `uv.lock`).
  - `uv sync` — install/refresh the environment from the lockfile.
  - `uv run <cmd>` — run a command inside the project venv (e.g. `uv run pytest`, `uv run alembic ...`).
- Commit `uv.lock`. Never hand-edit the venv or add a `requirements.txt`.
- Python is pinned to **3.13** (`.python-version`, `requires-python` in `pyproject.toml`).

## Layout

```
app/
├── main.py            # FastAPI app + router registration + CORS
├── core/              # config (pydantic-settings), db engine/session, security (admin JWT)
├── models/            # SQLModel tables + enums (the DB schema)
├── schemas/           # Pydantic request/response models (decoupled from tables)
├── services/          # status derivation, loan/admin events, barcode allocation, card PDFs (cards),
│                       #   xlsx import/export (spreadsheet), app settings, admin password (admin_auth),
│                       #   serializers, shared queries
├── templates/         # SVG card templates (item_tag.svg, user_id_card.svg) filled by services/cards
├── api/               # routers: auth, admin_users, admin_inventory, admin_history, admin_settings,
│                       #   kiosk, inventory, labels + deps + responses (shared pdf/xlsx helpers)
├── seed.py            # demo data (`make seed`)
└── tests/             # pytest against a real postgres:18 container (testcontainers — never SQLite)
alembic/               # migrations (env.py wires the async engine + SQLModel metadata)
```

## Conventions

- **Async everywhere.** Routes, services, and DB access are `async`. Use the `get_session`
  dependency; don't open ad-hoc engines outside `core/db.py` (tests are the exception).
- **Layering.** Routers stay thin: validate input, call a service, serialize output. Put domain
  rules in `services/`. Keep status/loan logic in `services/status.py` and `services/events.py` so
  every view agrees on the rules — don't reimplement "is it on loan?" in a router.
- **Event sourcing.** An item's availability *status* and a user's loans are *derived* from the
  `events` table, never stored. Status combines the loan state with a "sticky" availability set by
  the latest of `damage_report`/`loss_report`/`discard`/`mark_unavailable`/`restore`. When you add an
  action that affects availability, append an `Event` and update `services/status.py` — don't add a
  status column. (Stored fields like `Item.condition`, `Item.needs_review`, and `User.status` are
  physical/workflow state, not loan availability, so they live on the row.) **Filtering by status is
  server-side:** `services/queries.py::item_read_query` is the *SQL twin* of `status.py` — it derives
  status in Postgres (DISTINCT ON over `events` + a CASE mirroring `combine_status`) so the list
  endpoints can filter/sort by the derived status. Keep the two in sync; `test_item_read_query.py`
  asserts they agree across event histories. If you change the status rules, change both.
- **Enums as VARCHAR.** `Condition`/`EventType`/`ItemStatus`/`UserStatus` are stored as plain
  `VARCHAR` (`sa_type=String`), not native PG enums, so values change with no DB-type migration;
  validation happens via the `StrEnum` in the schemas.
- **Schemas vs models.** Tables live in `models/`; never return raw tables from the API — go
  through a `schemas/` read model (enriched via `services/serialize.py`).
- **Reserved words.** Table names are explicit (`users`, `groups`, ...) because `user`/`group` are
  reserved in Postgres. Keep that pattern for new tables.
- **Auth.** Admin routes depend on `require_admin` (validates the session JWT cookie). Kiosk and
  inventory routes are intentionally open (trusted LAN). Don't add auth to those without discussing.

## Migrations (Alembic)

**Stocky is deployed to real users. Every schema change ships with a migration — no exceptions.**

- Schema lives in `models/`. The baseline migration (`0001`) builds the schema from SQLModel
  metadata via `metadata.create_all`. It is the *starting point only* — never the mechanism for
  applying a later change.
- **Workflow for any model change:** edit `models/`, then `make migrate-create m="..."`,
  **read the generated revision** (autogenerate misses things — renames become drop+add, server
  defaults and constraints are often omitted, and `compare_type=True` catches column-type changes
  but not everything), fix it by hand where needed, then `make migrate`.
- **Include the data.** A migration that changes shape must also move the data — backfill new
  non-nullable columns, translate renamed enum values. Adding a `NOT NULL` column to a populated
  table fails without a default or a backfill step.
- **Write `downgrade()`.** It's the rollback path when a deploy goes wrong on the Pi.
- **Migrations are immutable.** Never edit one that's already committed; correct it with a new
  revision. Someone's database has already run the old one.
- **Never rebuild to fix a schema.** `make clean` destroys the volume and everything in it. It is a
  local-development tool. On any database with real data, the only path forward is a new migration.
- **Test the migration, not just the models.** Tests build the schema with `create_all`, so they
  validate where you're going and say nothing about whether the upgrade gets there. Run
  `make migrate` against a copy of real data before deploying.

## Testing & lint

- `uv run pytest` — tests run against a **real `postgres:18` container** (testcontainers), never
  SQLite. A Docker daemon must be running. The schema is created/dropped per test for isolation, so
  the exact production types (tz-aware timestamps, JSON, UUID) and queries are validated. Never swap
  in SQLite or a mocked DB to "make tests faster" — see golden rule #8 in the root CLAUDE.md.
- `uv run ruff check .` and `uv run ruff format .` — lint and format. FastAPI's `Depends`/`Cookie`
  defaults are whitelisted for bugbear B008.
- Add or update a test when you change behavior (a new loan rule, a new endpoint).
