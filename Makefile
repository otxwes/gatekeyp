.PHONY: setup install test test-verbose lint audit security clean docker-build docker-up docker-down typecheck format check

# Default target: show available commands
.DEFAULT_GOAL := help

help:
	@echo "Gatekeyp Development Commands"
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
	@echo "  make clean        - Remove build artifacts and caches"

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

# Docker targets
docker-build:
	docker build -t gatekeyp .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Clean up build artifacts and caches
clean:
	rm -rf .pytest_cache
	rm -rf __pycache__
	rm -rf src/__pycache__ src/*/__pycache__
	rm -rf tests/__pycache__
	rm -f *.db
	@echo "Cleaned build artifacts and caches"
