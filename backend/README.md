# Stocky backend

FastAPI + SQLModel API for Stocky. Managed with **uv** (never pip). See
[CLAUDE.md](CLAUDE.md) for conventions and [../stocky.md](../stocky.md) for the product spec.

```bash
uv sync                                  # install deps
uv run alembic upgrade head              # apply migrations
uv run python -m app.seed                # load demo data
uv run uvicorn app.main:app --reload     # run dev server (:8000)
uv run pytest                            # tests
uv run ruff check .                       # lint
```

API docs at http://localhost:8000/docs once running.
