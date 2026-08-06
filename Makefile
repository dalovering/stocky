# Stocky — dev & ops entrypoint.
# Backend is managed with uv (NEVER pip). Deployment uses docker-compose.
# Run `make help` for the list of targets.

# Load .env if present so DATABASE_URL etc. are available to local targets.
ifneq (,$(wildcard .env))
include .env
export
endif

COMPOSE := docker compose
BACKEND  := backend
FRONTEND := frontend

# Only the makefile(s) — the `include .env` above also lands in MAKEFILE_LIST, and `help` must
# not scan it for targets.
HELP_SOURCES := $(filter %Makefile %.mk,$(MAKEFILE_LIST))

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(HELP_SOURCES) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Docker-compose (deployment / full stack)
# ---------------------------------------------------------------------------
.PHONY: init-env
init-env: ## Generate a local .env with openssl-random secrets (won't overwrite existing)
	./scripts/gen-env.sh

.PHONY: build
build: ## Build all docker images
	$(COMPOSE) build

.PHONY: run
run: ## Build and start the full stack (postgres 18 + backend + frontend)
	$(COMPOSE) up -d --build

.PHONY: up
up: run ## Alias for `run`

.PHONY: start
start: ## Start the full stack WITHOUT rebuilding (fast restart; run `make build` first if code changed)
	$(COMPOSE) up -d

.PHONY: down
down: ## Stop the full stack
	$(COMPOSE) down

.PHONY: clean
clean: ## Stop the stack and remove volumes (DESTROYS DB DATA)
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Show running services
	$(COMPOSE) ps

.PHONY: db
db: ## Start only Postgres 18 (for local `make dev`) and wait until it's ready
	$(COMPOSE) up -d db
	@echo "Waiting for Postgres to be healthy..."
	@tries=0; \
	until [ "$$(docker inspect -f '{{.State.Health.Status}}' "$$($(COMPOSE) ps -q db)" 2>/dev/null)" = "healthy" ]; do \
		tries=$$((tries+1)); \
		if [ $$tries -ge 60 ]; then echo "Postgres did not become healthy in time." >&2; exit 1; fi; \
		sleep 1; \
	done
	@echo "Postgres is ready on $${POSTGRES_HOST:-localhost}:$${POSTGRES_PORT:-5432}."

.PHONY: db-down
db-down: ## Stop the Postgres container used by `make dev`
	$(COMPOSE) stop db

# ---------------------------------------------------------------------------
# Database / migrations (Alembic, via uv)
# ---------------------------------------------------------------------------
.PHONY: migrate
migrate: ## Apply all pending DB migrations
	cd $(BACKEND) && uv run alembic upgrade head

.PHONY: migrate-create
migrate-create: ## Autogenerate a migration: make migrate-create m="message"
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

.PHONY: migrate-down
migrate-down: ## Roll back the last migration
	cd $(BACKEND) && uv run alembic downgrade -1

.PHONY: seed
seed: ## Load demo data (groups, users, item types, items, barcodes)
	cd $(BACKEND) && uv run python -m app.seed

.PHONY: reset-admin-pass
reset-admin-pass: ## Set a new admin password (prompts) — recovery when locked out of /admin
	cd $(BACKEND) && uv run python -m app.reset_admin_password

# ---------------------------------------------------------------------------
# Local development (no docker) — backend via uv, frontend via npm
# ---------------------------------------------------------------------------
.PHONY: install
install: install-backend install-frontend ## Install all dependencies

.PHONY: install-backend
install-backend: ## Sync backend deps with uv
	cd $(BACKEND) && uv sync

.PHONY: install-frontend
install-frontend: ## Install frontend deps with npm
	cd $(FRONTEND) && npm install

.PHONY: dev
dev: db migrate ## Run backend (uv) and frontend (npm) locally in parallel (starts Postgres first)
	@echo "Starting backend (:8000) and frontend (:3000). Ctrl-C to stop both."
	@trap 'kill 0' INT TERM; \
	( cd $(BACKEND) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 ) & \
	( cd $(FRONTEND) && npm run dev ) & \
	wait

.PHONY: dev-backend
dev-backend: db migrate ## Run only the backend locally (uv), starting Postgres first
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: dev-frontend
dev-frontend: ## Run only the frontend locally (npm dev server — compiles on demand; not for the Pi)
	cd $(FRONTEND) && npm run dev

.PHONY: prod-frontend
prod-frontend: ## Build + serve the frontend in production mode (no per-page compile; best for the Pi without docker)
	cd $(FRONTEND) && npm run build && npm start

# ---------------------------------------------------------------------------
# Quality: tests, lint, format
# ---------------------------------------------------------------------------
.PHONY: test
test: test-backend test-frontend ## Run all tests

.PHONY: test-backend
test-backend: ## Run backend tests (pytest via uv)
	cd $(BACKEND) && uv run pytest

.PHONY: test-frontend
test-frontend: ## Run frontend tests
	cd $(FRONTEND) && npm test

.PHONY: lint
lint: ## Lint backend (ruff) and frontend (eslint)
	cd $(BACKEND) && uv run ruff check .
	cd $(FRONTEND) && npm run lint

.PHONY: format
format: ## Format backend (ruff) and frontend (prettier)
	cd $(BACKEND) && uv run ruff format .
	cd $(FRONTEND) && npm run format
