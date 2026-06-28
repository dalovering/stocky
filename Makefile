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

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Docker-compose (deployment / full stack)
# ---------------------------------------------------------------------------
.PHONY: build
build: ## Build all docker images
	$(COMPOSE) build

.PHONY: run
run: ## Start the full stack (postgres 18 + backend + frontend)
	$(COMPOSE) up -d --build

.PHONY: up
up: run ## Alias for `run`

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
dev: ## Run backend (uv) and frontend (npm) locally in parallel
	@echo "Starting backend (:8000) and frontend (:3000). Ctrl-C to stop both."
	@trap 'kill 0' INT TERM; \
	( cd $(BACKEND) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 ) & \
	( cd $(FRONTEND) && npm run dev ) & \
	wait

.PHONY: dev-backend
dev-backend: ## Run only the backend locally (uv)
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: dev-frontend
dev-frontend: ## Run only the frontend locally (npm)
	cd $(FRONTEND) && npm run dev

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
