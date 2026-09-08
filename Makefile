.PHONY: setup install test test-verbose lint audit security serve serve-lite backup clean docker-build docker-up docker-down typecheck format check

# Default target: show available commands
.DEFAULT_GOAL := help

help:
	@echo "gatekeyp Development Commands"
	@echo "============================="
	@echo "  make setup        - Create virtual environment and install all dependencies (uv)"
	@echo "  make install      - Sync dependencies from lockfile (uv)"
	@echo "  make test         - Run the full test suite"
	@echo "  make test-verbose - Run tests with verbose output"
	@echo "  make lint         - Run ruff linter"
	@echo "  make typecheck    - Run ty type checker"
	@echo "  make format       - Auto-format code with ruff"
	@echo "  make audit        - Run dependency vulnerability audit (pip-audit)"
	@echo "  make security     - Run security audit tests only"
	@echo "  make docker-build - Build the Docker image"
	@echo "  make docker-up    - Start services with docker compose"
	@echo "  make docker-down  - Stop services with docker compose"
	@echo "  make serve        - Run dev server (full profile) in the foreground"
	@echo "  make serve-lite   - Run dev server (lite/ephemeral-only profile)"
	@echo "  make backup       - Timestamped backup of keys.db"
	@echo "  make clean        - Remove build artifacts (databases are preserved)"

# Set up virtual environment and install all dependencies
setup:
	uv sync --all-groups
	@echo "Virtual environment created at .venv/"
	@echo "Activate with: source .venv/bin/activate"

# Sync dependencies from lockfile
install:
	uv sync --all-groups

# Run the full test suite
test:
	uv run pytest

# Run tests with verbose output
test-verbose:
	uv run pytest -v

# Run security audit tests only
security:
	uv run pytest tests/test_security_audit.py -v

# Run ruff linter
lint:
	uv run ruff check src/ tests/

# Run ty type checker
typecheck:
	uv run ty check src/

# Auto-format code with ruff
format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

# Run dependency vulnerability audit
audit:
	uv run pip-audit

# Start the dev server in the foreground from the repo root (Ctrl-C to stop).
# Secrets come from .env.dev (gitignored) so the same keys.db stays readable
# across restarts. See .env.example for the variable reference.
serve:
	@if [ ! -f .env.dev ]; then echo "Missing .env.dev - create it with GATEKEYP_MASTER_KEY and GATEKEYP_HMAC_SECRET (see .env.example)"; exit 1; fi
	@set -a && . ./.env.dev && set +a && uv run python -m src.api.server

# Start the lite (ephemeral-only) profile in the foreground.
# Mounts only: POST /api/lite/events, GET /i/{event_id}, the public flyer
# route and /health. Standard API routes are NOT exposed in this profile.
serve-lite:
	@if [ ! -f .env.dev ]; then echo "Missing .env.dev - create it with GATEKEYP_MASTER_KEY and GATEKEYP_HMAC_SECRET (see .env.example)"; exit 1; fi
	@set -a && . ./.env.dev && set +a && GATEKEYP_PROFILE=lite uv run python -m src.api.server

# Timestamped backup of the production database. Run this before migrations
# or any destructive operation - keys.db is the only copy of event keys.
backup:
	@if [ ! -f keys.db ]; then echo "No keys.db found - nothing to back up"; exit 1; fi
	@cp keys.db keys.db.bak-$$(date +%Y%m%d)
	@echo "Backed up keys.db to keys.db.bak-$$(date +%Y%m%d)"

# Docker targets
docker-build:
	docker build -t gatekeyp .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Clean up build artifacts and caches.
# NOTE: database files (keys.db*) are NEVER removed here - they hold the only
# copy of event keys. Run `make backup` before any destructive operation.
clean:
	rm -rf .pytest_cache
	rm -rf __pycache__
	rm -rf src/__pycache__ src/*/__pycache__
	rm -rf tests/__pycache__
	rm -rf .ruff_cache
	@echo "Cleaned build artifacts and caches (databases are preserved)"
