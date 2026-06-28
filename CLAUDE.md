# Stocky — project guide for Claude

Stocky is a lightweight inventory-management app for classroom supplies. It tracks which
students have borrowed which items via barcode/ID-card scanning. It must run comfortably on a
**Raspberry Pi 4**, so keep everything lightweight and ARM-friendly.

The product spec is in [stocky.md](stocky.md). Read it before changing behavior.

---

## 🔒 Golden Rules — never violate these

These come straight from the spec. They are non-negotiable.

1. **PostgreSQL 18 — DO NOT DOWNGRADE.** The database is pinned to `postgres:18`. Never change
   it to an older major version, even "temporarily" or to fix a build.
2. **UV only — never pip.** All Python dependency, virtualenv, and run/stop operations go through
   [`uv`](https://docs.astral.sh/uv/). Never run `pip install`, never hand-edit a venv, never add
   `requirements.txt`. Use `uv add`, `uv sync`, `uv run`.
3. **Python 3.13.** Pinned in `backend/pyproject.toml` and `backend/.python-version`.
4. **FastAPI 0.138 + SQLModel** for the backend.
5. **Next.js 16.2 + Radix UI** (minimal styling) for the frontend, managed with **npm**.
6. **Makefile drives the dev workflow** (`make run`, `make down`, etc.) and **docker-compose**
   drives deployment. Add new operational commands as Makefile targets, not ad-hoc scripts.
7. **Keep it Pi-4 lightweight.** Prefer small images, avoid heavy native deps, don't add a service
   unless it earns its keep.

If a task seems to require breaking one of these, stop and ask the user instead.

---

## Repo layout

```
stocky/
├── CLAUDE.md            # this file — project-wide rules
├── Makefile             # dev + ops entrypoint (uv + docker-compose)
├── docker-compose.yml   # postgres:18, backend, frontend
├── .env.example         # copy to .env and fill in
├── backend/             # FastAPI + SQLModel API (see backend/CLAUDE.md)
└── frontend/            # Next.js + Radix UI app (see frontend/CLAUDE.md)
```

`backend/CLAUDE.md` and `frontend/CLAUDE.md` hold the rules specific to each side. When you change
conventions in a subtree, update that subtree's CLAUDE.md in the same commit.

---

## How to run

```bash
cp .env.example .env        # then edit ADMIN_PASSWORD / secrets
make run                    # docker-compose up: postgres 18 + backend + frontend
make migrate                # apply DB migrations
make seed                   # load demo data so the kiosk works immediately
make down                   # stop everything

make dev                    # run backend (uv) + frontend (npm) locally, no docker
make test                   # backend + frontend tests
make lint                   # ruff + eslint
make format                 # ruff format + prettier
```

The three views once running:
- **Admin** — `http://localhost:3000/admin` (requires admin login at `/login`)
- **Kiosk** — `http://localhost:3000/kiosk` (barcode-driven check-in/out)
- **Inventory** — `http://localhost:3000/inventory` (read-only browse)

---

## Architecture in one paragraph

The backend is an async FastAPI app over PostgreSQL 18 via SQLModel + asyncpg, with Alembic
migrations. Item history is **event-sourced**: every checkout/checkin/damage/loss is an `Event`
row, and an item's *current status* and a user's *current loans* are derived from those events
(see `backend/app/services/status.py`). Admin endpoints are guarded by a simple password →
JWT-cookie scheme; the kiosk and read-only inventory endpoints are open on the trusted LAN and
identify users by scanned barcode. The frontend is a Next.js App Router app using Radix UI; the
kiosk listens for barcode scans globally (no input focus required).

---

## Code-management / git conventions

Follow these so history stays clean and the repo is easy to push to GitHub and review.

- **Conventional Commits.** `type(scope): summary` — e.g. `feat(kiosk): add global barcode listener`,
  `fix(api): reject double checkout`, `chore(ci): ...`. Types: `feat`, `fix`, `docs`, `refactor`,
  `test`, `chore`, `build`.
- **Small, focused commits.** One logical change each. Don't mix refactors with features. The diff
  should be reviewable on its own.
- **Commit incrementally as you work.** During any multi-step task, commit at each sensible
  milestone (scaffolding, a data layer, an API surface, a UI view) rather than dumping everything
  in one giant commit at the end. Each commit should build and pass lint/tests on its own where
  practical, and tell a clear story of how the change was assembled.
- **Branch per feature/fix.** Work on `feat/...` or `fix/...` branches off `main`; keep `main`
  releasable. Open PRs for review rather than pushing straight to `main`.
- **Never commit secrets.** `.env` is git-ignored; commit `.env.example` with placeholder values
  only. No passwords, tokens, or keys in code or history.
- **Don't commit generated/vendor artifacts.** `node_modules/`, `.next/`, `.venv/`, build output,
  and caches are git-ignored. **Do** commit lockfiles (`uv.lock`, `package-lock.json`).
- **Keep the tree green.** Run `make lint` and `make test` before committing. Don't commit code
  that fails them.
- **Migrations are immutable once applied/committed.** Add a new Alembic migration to change schema;
  never edit a migration that's already in history.
- **Write meaningful messages.** Explain the *why* in the body when it isn't obvious from the diff.
