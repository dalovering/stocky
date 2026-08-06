# Contributing to Stocky

Thanks for taking a look. Stocky is a small, opinionated project — it runs on a Raspberry Pi 4 in
a classroom, so a lot of decisions that look arbitrary are really about staying light and
predictable on that hardware.

Issues are welcome from anyone. For code, please open an issue first if the change is more than a
small fix, so we can agree on the approach before you spend time on it.

## Non-negotiables

These are the rules a pull request will be sent back for. They're the short version of
[CLAUDE.md](CLAUDE.md), which has the reasoning.

1. **PostgreSQL 18.** Pinned. Never downgraded, not even temporarily to fix a build.
2. **uv, never pip.** All Python dependency and run operations go through
   [uv](https://docs.astral.sh/uv/) — `uv add`, `uv sync`, `uv run`. No `requirements.txt`, no
   hand-edited virtualenv.
3. **Python 3.13**, **FastAPI + SQLModel** on the backend; **Next.js + Radix UI**, managed with
   npm, on the frontend.
4. **No fakes.** No SQLite (not even in tests), no mocked database, no stubbed API layer, no
   sample data hardcoded into the frontend. Tests run against a real `postgres:18` container via
   testcontainers, so a Docker daemon has to be running. A fake that hides a real-stack bug is
   worse than no test — that's not hypothetical here, SQLite once hid a timezone-type bug.
5. **Every schema change ships with an Alembic migration**, in the same commit. Stocky is
   deployed with real data; a migration is the only way a schema change reaches it. Never
   propose rebuilding a database to apply one.
6. **Keep it Pi-4 lightweight.** Small images, no heavy native dependencies, no new service
   unless it clearly earns its place.

## Getting set up

```bash
make init-env     # generate .env with random secrets
make run          # postgres 18 + backend + frontend, in docker
make seed         # demo data, so the kiosk has something to scan
```

The first visit to `/admin` prompts you to create an admin password. Locked out later?
`make reset-admin-pass`.

For local work without docker, `make dev` runs the backend and frontend directly. `make help`
lists everything.

## Before you open a pull request

```bash
make lint         # ruff + eslint
make test         # backend (real postgres container) + frontend
```

Both must pass. There's no CI yet, so this is on you.

## Commits and pull requests

- **[Conventional Commits](https://www.conventionalcommits.org/)** — `type(scope): summary`, e.g.
  `fix(kiosk): reject double checkout`. Types: `feat`, `fix`, `docs`, `refactor`, `test`,
  `chore`, `build`.
- **One logical change per commit.** Don't mix a refactor into a feature; the diff should be
  reviewable on its own.
- **Explain the why in the body** when it isn't obvious from the diff. What the code does is
  already in the code.
- **Branch from `main`** as `feat/...` or `fix/...`, and open a PR rather than pushing to `main`.
- **Update the docs in the same commit.** `CLAUDE.md`, `backend/CLAUDE.md`, and
  `frontend/CLAUDE.md` describe the conventions of their subtree; if you change one, say so
  there too.

## Things to know before you change behavior

- **Item status is derived, not stored.** Availability comes from the event log
  (`services/status.py`), and `services/queries.py` is its SQL twin so the same rules can filter
  and sort in Postgres. If you change the status rules, change both — there's a test that
  asserts they agree.
- **Derive and filter server-side.** Searching, filtering, sorting, and pagination belong in the
  API, not in the browser. The Pi should never ship a whole table to a client that then whittles
  it down.
- **The kiosk and read-only inventory endpoints are intentionally unauthenticated** on a trusted
  LAN. Don't add auth to them without discussing it first, and see [SECURITY.md](SECURITY.md)
  for the threat model.

## Reporting bugs and security issues

Bugs and feature requests go in [Issues](https://github.com/dalovering/stocky/issues).

**Security problems don't** — see [SECURITY.md](SECURITY.md) for private reporting.

If a bug report involves real data, **please redact it**. Stocky handles student names, and an
issue on a public repository is permanent and world-readable. Screenshots and spreadsheet
exports are the easy ways to leak them by accident.
