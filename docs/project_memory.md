# Project Memory

This document serves as the durable, self-improving memory for the Gatekeyp project. It captures lessons learned, tooling solutions, process improvements, and coding practices discovered during development. **This is a living document** — update it whenever you encounter a worthwhile lesson.

## How to Use This Document

- **Before starting a task**: Skim this document for relevant lessons that may apply.
- **During a task**: If you hit an error or discover a better approach, note it here.
- **After a task**: Review what you learned and add any new lessons.
- **When updating**: Add entries to the appropriate section, keep entries concise and actionable.

---

## 1. Tooling Solutions & Error Fixes

### 1.1 uv (Package Manager)

- **uv sync creates a virtual environment automatically** — no need to manually create one with `python -m venv`.
- **Use `uv run <command>`** to execute tools within the project environment (e.g., `uv run pytest`, `uv run ruff check`).
- **Dependency groups in `pyproject.toml`** keep dev/test/audit dependencies separate from runtime dependencies.
- **`uv.lock` provides reproducible builds** — always commit it to version control.
- **`uv sync` is idempotent** — safe to run repeatedly; it only installs what's missing.

### 1.2 Pre-commit Hooks

- **`pyupio/safety` hook is broken** — the repo at rev `3.2.0` has an invalid `.pre-commit-hooks.yaml` manifest. Use `pip-audit` instead (via `uv run pip-audit` or the `audit` dependency group).
- **`pip-audit` as a pre-commit hook can fail on Apple Silicon** — the pre-commit isolated environment may install x86_64 wheels that are incompatible with arm64. Run `pip-audit` via `uv run pip-audit` instead of as a pre-commit hook.
- **Pre-commit hooks may modify files** (e.g., `ruff format`, `end-of-file-fixer`) — always run `pre-commit run --all-files` before committing, and re-stage files after hooks modify them.
- **When a commit is blocked by pre-commit**, the hooks have already modified files. Re-stage with `git add -A` and retry the commit.
- **`pre-commit install`** installs the git hook that runs on every commit. Run it once after setting up the project.

### 1.3 Ruff (Linter & Formatter)

- **Ruff's `ALL` ruleset is aggressive** — use `per-file-ignores` for test files to suppress rules that don't apply (e.g., `S105`/`S106` for hardcoded passwords in test fixtures, `PT009` for unittest-style assertions).
- **`ruff format` and `ruff check` are separate commands** — run both to ensure code is both formatted and lint-clean.
- **Ruff can auto-fix many issues** with `ruff check --fix` — run this before manually fixing.
- **Common rules to ignore for tests**: `ANN001`, `ANN201`, `ANN202`, `CPY001`, `ERA001`, `PLC0415`, `PT009`, `PT011`-`PT027`, `PTH100`, `PTH120`, `S105`-`S108`, `SLF001`, `TID252`.

### 1.4 Ty (Type Checker)

- **Ty is a fast Python type checker** — use `uv run ty check src/` to type-check the source code.
- **Type narrowing with `isinstance()`** — when a variable can be `None` or a specific type, use `isinstance()` checks to narrow the type before accessing attributes.
- **Ty may flag issues that mypy doesn't** — always run both if available.

### 1.5 Docker

- **Multi-stage builds** keep the final image small — use a builder stage for dependencies and a runtime stage for the application.
- **`uv` works well in Docker** — use `uv sync --frozen` in the builder stage for reproducible installs.
- **Use `--no-cache-dir`** with pip to avoid caching issues in containers.

### 1.6 MCP Servers

- **MCP servers are configured in `.mcp.json`** — each server has a `command`, `args`, and `env` configuration.
- **GitHub MCP server** requires a `GITHUB_PERSONAL_ACCESS_TOKEN` environment variable.
- **Filesystem MCP server** provides file read/write/search capabilities.
- **Fetch MCP server** provides web content fetching.

### 1.7 Sub-Agents

- **Sub-agents are configured in `.agents/workflows.json`** — each workflow defines a prompt template and expected output.
- **Use sub-agents for parallel research** — they can explore different parts of the codebase simultaneously.
- **Sub-agents are most useful for** security audits, dependency audits, and code reviews.

---

## 2. Process Improvements

### 2.1 Development Workflow

- **Always run the full verification suite before committing**: `uv run pytest tests/ -q && uv run ruff check . && uv run ty check src/`.
- **Run `pre-commit run --all-files`** before committing to catch issues early.
- **Commit in logical units** — separate infrastructure changes from feature changes from documentation changes.
- **Use `git add -A` after pre-commit modifies files** — hooks may reformat or fix files, and you need to re-stage them.

### 2.2 Testing

- **Property-based testing with Hypothesis** catches edge cases that example-based tests miss.
- **Test fixtures in `tests/conftest.py`** provide shared setup for all tests.
- **Test helpers in `tests/helpers.py`** provide reusable utilities.
- **Security audit tests** should verify that hardcoded secrets, weak auth, and permissive security are not present.

### 2.3 Documentation

- **Keep documentation in sync with code** — when you change behavior, update the relevant docs.
- **Use the `skills/` directory for reusable instruction sets** — each skill has YAML frontmatter with `name` and `description`.
- **The `skills_manifest.md` tracks all installed skills** — update it when adding or removing skills.

---

## 3. Coding Practices

### 3.1 Python

- **Use modern Python (3.11+)** — take advantage of `match` statements, `Self` type, `TypeVarTuple`, etc.
- **Use type hints everywhere** — Ty and Ruff will enforce this.
- **Prefer `pathlib.Path` over `os.path`** — it's more modern and type-safe.
- **Use `cryptography` for crypto operations** — it's well-maintained and audited.
- **Use `argon2-cffi` for password hashing** — Argon2 is the recommended password hashing algorithm.

### 3.2 Security

- **Never hardcode secrets** — use environment variables (see `.env.example`).
- **Use `secrets` module for cryptographic random values** — not `random`.
- **Validate all inputs** — especially from external sources.
- **Follow the threat model** in `docs/threat_model.md` — it defines the security boundaries.

### 3.3 Testing

- **Write tests before or alongside code** — test-driven development catches bugs early.
- **Use property-based testing for** serialization, crypto operations, and data validation.
- **Test both happy paths and edge cases** — empty inputs, invalid inputs, boundary values.

---

## 4. Project-Specific Knowledge

### 4.1 Architecture

- **Gatekeyp is a privacy-preserving, federated event-organizing toolkit**.
- **Core components**:
  - `src/core/key_manager.py` — Key system (HMAC-SHA256, Argon2id, rotation, revocation)
  - `src/core/content_manager.py` — Media assets, bulletins, comments (encrypted at rest)
  - `src/core/event_lifecycle.py` — Event creation, access keys, decommissioning
  - `src/api/gateway.py` — Rate-limited API gateway
  - `src/api/server.py` — FastAPI HTTP server + static web UI
  - `src/db/database_handler.py` — SQLite with encryption-at-rest (Fernet/AES-GCM)
- **Key system**: Uses HMAC-SHA256 keyed hashing (per-instance secret) and optional Argon2id for higher-cost verification.
- **Federation**: See `docs/federation_specification.md` for the federation design.
- **Database schema**: See `docs/database_schema.md` for the schema design.
- **Key specification**: See `docs/key_specification.md` for the Key system design.
- **Web UI**: `web/` directory contains the static frontend (HTML, CSS, JS) served by the FastAPI server.

### 4.2 Roadmap

- **Phase 1**: Core Architecture (Key logic, database, secure backend) ✅
- **Phase 2**: Content & Communication (flyers, descriptions, media) ✅
- **Phase 3**: Frontend & UX/UI Design
- **Phase 4**: Map & Navigation (OpenStreetMap, geofencing)
- **Phase 5**: Payment & Ticketing (Monero)

---

## 5. Self-Improvement Log

### 2026-08-02 — Initial Infrastructure Modernization

**What was done:**
- Migrated from `requirements.txt` to `pyproject.toml` with `uv` as the package manager
- Added Docker containerization
- Added MCP server configuration
- Added sub-agent workflows
- Added pre-commit lifecycle hooks
- Added security audit tests and property-based testing
- Added 4 new skills (modern_python, insecure_defaults, property_based_testing, supply_chain_audit)

**Lessons learned:**
1. `pyupio/safety` pre-commit hook is broken — use `pip-audit` instead
2. `pip-audit` as a pre-commit hook can fail on Apple Silicon due to architecture mismatch — run it via `uv run pip-audit` instead
3. Pre-commit hooks modify files — always re-stage after running them
4. Ruff's `ALL` ruleset requires extensive `per-file-ignores` for test files
5. `uv sync` automatically creates a virtual environment — no manual venv creation needed
6. Type narrowing with `isinstance()` is essential for Ty to pass on optional values

**Next steps:**
- Continue building out Phase 1 (Core Architecture)
- Add CI/CD pipeline (GitHub Actions)
- Add more property-based tests for crypto operations
- Consider adding a `docs/decisions.md` for architectural decision records (ADRs)

### 2026-08-02 — Phase 2: Content & Communication Layer

**What was done:**
- Implemented `ContentManager` for media assets (flyers, images, documents) with encryption-at-rest
- Implemented secure communication boards (bulletins with encrypted bodies, threaded comments)
- Implemented `EventLifecycleManager` for end-to-end event orchestration (creation, access keys, decommissioning)
- Added FastAPI HTTP server (`src/api/server.py`) with RESTful endpoints for all features
- Added static web UI (`web/`) — mobile-first, privacy-preserving frontend
- Added `fastapi`, `python-multipart`, and `uvicorn` dependencies
- Expanded test suite from 77 to 123 tests (all passing)

**Lessons learned:**
1. FastAPI's `UploadFile` requires `python-multipart` for form data handling
2. Static file serving in FastAPI is straightforward with `StaticFiles` and `FileResponse`
3. CORS middleware is needed for development when the frontend and API are on different origins
4. Content managers should share the same `DatabaseHandler` and `KeyManager` instances to maintain consistency
5. Event lifecycle management benefits from a dedicated manager class that orchestrates multiple services
6. MIME-type validation and size limits are essential for media upload security

**Next steps:**
- Begin Phase 3: Frontend & UX/UI Design (refine web UI, accessibility, responsive polish)
- Add CI/CD pipeline (GitHub Actions)
- Consider adding a `docs/decisions.md` for architectural decision records (ADRs)
