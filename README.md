# Gatekeyp

A privacy-preserving, federated event-organizing toolkit with a secure "Key" system that gates access to event content.

## Overview

Gatekeyp is designed to help communities organize events while prioritizing:
- **Data minimization** - Collect only what's necessary
- **Local-first architecture** - Resolve keys locally whenever possible
- **Resistance to surveillance** - No third-party tracking, minimal data retention
- **Technological autonomy** - Move away from corporate infrastructure and dependencies on capitalist platforms, empowering communities to own and control their organizing tools

## Core Features

- **Key Management**: Cryptographically secure, opaque keys that gate access to restricted content (event locations, contact details, etc.)
  - HMAC-SHA256 keyed hashing (per-instance secret) — resistant to offline brute-force
  - Optional Argon2id for higher-cost verification
  - Key rotation and revocation support
  - Minimum key entropy enforcement (128 bits)
  - Constant-time comparison (`hmac.compare_digest`)
- **Federated Validation**: Support for multi-instance key validation without a central registry
- **Database Schema**: SQLite-based storage with encryption-at-rest for sensitive payloads
  - Fernet/AES-GCM encryption for content payloads and event locations
  - `key_content_links` join table for many-to-many key ↔ content mapping
  - `created_at`, `location_data`, `owner_id`, and revocation fields
- **API Gateway**: Rate-limited, validated endpoints for key verification
  - Per-IP and per-key rate limiting with exponential backoff
  - Hardened input validation
  - Structured audit logging (no PII)

## Project Structure

```
├── .agents/         # Sub-agent workflow definitions
├── .mcp.json        # MCP server configuration
├── .pre-commit-config.yaml  # Lifecycle hooks
├── docs/            # Specifications and threat model
├── src/
│   ├── api/         # API gateway
│   ├── core/        # Key management logic
│   └── db/          # Database handler
├── tests/           # Unit, integration, property-based, and security tests
├── pyproject.toml   # Modern dependency management (uv)
├── uv.lock          # Locked dependency versions (commit this!)
├── Dockerfile       # Containerization
├── docker-compose.yml
├── Makefile         # Development commands
├── pytest.ini
└── roadmap.md
```

## Development

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — fast Python package manager
- [Docker](https://www.docker.com/) (optional, for containerized deployment)

### Setup

```bash
# Install uv (macOS)
brew install uv

# Create virtual environment and install all dependencies
make setup
# or: uv sync --all-groups
```

### Required Environment Variables

Gatekeyp uses **fail-secure** configuration: the application refuses to start if these are missing.

```bash
# Fernet-compatible master key for encryption-at-rest
# Generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
export GATEKEYP_MASTER_KEY="your-fernet-key-here"

# Per-instance secret for HMAC keyed hashing
export GATEKEYP_HMAC_SECRET="your-hmac-secret-here"
```

See [.env.example](.env.example) for a template.

### Running Tests

```bash
make test
# or: uv run pytest
```

The test suite includes:
- **Unit tests** for key management, database handler, and rate limiter
- **Integration tests** for the full request flow (Gateway → KeyManager → DatabaseHandler)
- **Property-based tests** (Hypothesis) for key hashing, generation, federation parsing, and encryption roundtrips
- **Security audit tests** validating the threat model checklist

### Code Quality

```bash
make lint        # ruff linter
make typecheck   # ty type checker
make format      # auto-format with ruff
make audit       # dependency vulnerability audit (pip-audit)
```

### Lifecycle Hooks

Pre-commit hooks are configured in [.pre-commit-config.yaml](.pre-commit-config.yaml):

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

Hooks run: ruff lint + format, mypy type checking, safety dependency audit, and general file checks.

### Containerization

```bash
# Build the image
make docker-build

# Start services (requires GATEKEYP_MASTER_KEY and GATEKEYP_HMAC_SECRET in .env)
make docker-up

# Stop services
make docker-down
```

The Dockerfile uses a multi-stage build with a non-root user, read-only filesystem, and dropped capabilities for security.

### MCP Servers

MCP servers are configured in [.mcp.json](.mcp.json) for:
- **security-audit**: Dependency vulnerability scanning (pip-audit)
- **code-quality**: Ruff linting
- **type-check**: Ty type checking

### Sub-Agent Workflows

Parallel sub-agent workflows are defined in [.agents/workflows.json](.agents/workflows.json):
- **security-review**: Parallel dependency audit, code security review, and test coverage analysis
- **code-quality**: Parallel lint, type-check, and modern Python review
- **documentation**: Parallel docs and skill alignment checks

## Roadmap

See [roadmap.md](roadmap.md) for the full development roadmap, including:
- Phase 0: Foundation & Hardening ✅
- Phase 1: Core Architecture (Security-Hardened) ✅
- Phase 2: Content & Communication Layer
- Phase 3: Frontend & UX/UI Design
- Phase 4: Map & Navigation (Privacy-Preserving)
- Phase 5: Payment & Ticketing System

## Security

See [docs/threat_model.md](docs/threat_model.md) for the complete threat model, including adversaries, trust boundaries, and mitigations.

## License

TBD
