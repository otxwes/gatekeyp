# Gatekeyp

A privacy-preserving, federated event-organizing toolkit with a secure "Key" system that gates access to event content.

## Overview

Gatekeyp is designed to help communities organize events while prioritizing:
- **Data minimization** - Collect only what's necessary
- **Local-first architecture** - Resolve keys locally whenever possible
- **Resistance to surveillance** - No third-party tracking, minimal data retention

## Core Features

- **Key Management**: Cryptographically secure, opaque keys that gate access to restricted content (event locations, contact details, etc.)
- **Federated Validation**: Support for multi-instance key validation without a central registry
- **Database Schema**: SQLite-based storage with encryption-at-rest for sensitive payloads
- **API Gateway**: Rate-limited, validated endpoints for key verification

## Project Structure

```
├── docs/           # Specifications and threat model
├── src/
│   ├── api/        # API gateway
│   ├── core/       # Key management logic
│   └── db/         # Database handler
├── tests/          # Unit and integration tests
├── requirements.txt
└── roadmap.md
```

## Development

### Prerequisites
- Python 3.11+
- `python3` (not `python`)

### Setup

```bash
pip install -r requirements.txt
```

### Running Tests

```bash
python3 -m pytest
```

## Roadmap

See [roadmap.md](roadmap.md) for the full development roadmap, including:
- Phase 0: Foundation & Hardening ✅
- Phase 1: Core Architecture (Security-Hardened)
- Phase 2: Map & Navigation (Privacy-Preserving)
- Phase 3: Content & Communication Layer
- Phase 4: Payment & Ticketing System
- Phase 5: Frontend & UX/UI Design

## Security

See [docs/threat_model.md](docs/threat_model.md) for the complete threat model, including adversaries, trust boundaries, and mitigations.

## License

TBD