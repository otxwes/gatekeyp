# Roadmap: Gatekeyp

## Project Objectives
- Build a privacy-preserving, federated event-organizing toolkit.
- Implement a secure "Key" system that gates access to event content.
- Prioritize data minimization, local-first architecture, and resistance to surveillance.
- Follow a security-first, test-driven development process.

---

## Phase 0: Foundation & Hardening ✅
*Goal: Fix critical bugs, establish package structure, and document the threat model.*

- [x] Fix import bugs in `key_manager.py` (missing `DatabaseHandler`, `datetime`).
- [x] Fix import bugs in `gateway.py` (missing `KeyManager`, `DatabaseHandler`, `Dict`, `Any`).
- [x] Add package structure (`__init__.py` for `src`, `src/core`, `src/db`, `src/api`, `tests`).
- [x] Expand `.gitignore` (Python, DB, env, IDE, OS artifacts).
- [x] Add `requirements.txt` (cryptography, argon2-cffi, pytest).
- [x] Write `docs/threat_model.md` (adversaries, trust boundaries, mitigations).
- [x] Verify all 6 existing unit tests pass.
- [x] Verify `src.api.gateway` and `src.core.key_manager` import cleanly.
- [x] Fix architectural bug: `KeyManager` now accepts a shared `DatabaseHandler` so Gateway and KeyManager use the same connection.
- [x] Write integration tests for the full request flow (Gateway → KeyManager → DatabaseHandler) — 7 tests covering success, invalid input, missing content, expired keys, and event fallback.
- [x] All 13 tests pass.

## Phase 1: Core Architecture (Security-Hardened) ✅
*Goal: Harden key management, database schema, and API gateway.*

### Key Management
- [x] Replace plain SHA-256 with HMAC-SHA256 (keyed by per-instance secret) for stored key verification.
- [x] Add optional Argon2id support for higher-cost key verification.
- [x] Add key rotation and revocation support.
- [x] Enforce minimum key entropy at generation (128 bits / 16 bytes).
- [x] Add constant-time key comparison (`hmac.compare_digest`).
- [x] Fail-secure: require `GATEKEYP_HMAC_SECRET` env var; refuse to start without it.

### Database
- [x] Add `created_at`, `location_data` columns to schema.
- [x] Add `key_content_links` join table (many-to-many key ↔ content mapping).
- [x] Add encryption-at-rest for sensitive payloads (Fernet/AES-GCM with master key).
- [x] Add federation fields (owner identifier prefix) to schema.
- [x] Add key revocation fields (`revoked`, `revoked_at`).
- [x] Fail-secure: require `GATEKEYP_MASTER_KEY` env var; refuse to start without it.
- [x] Add schema migration for backward compatibility with existing databases.

### Gateway
- [x] Add rate limiting (per-IP and per-key) with exponential backoff.
- [x] Harden input validation (type checks, length limits, whitespace rejection).
- [x] Add structured audit logging (no PII, no raw keys).
- [x] Rate limiting resets on successful authentication.

### Tests
- [x] Unit tests for negative/edge cases (invalid, expired, revoked keys; brute-force attempts; unauthorized content access).
- [x] Integration tests for the full request flow.
- [x] Property-based tests (Hypothesis) for key hashing, generation, federation parsing, and encryption roundtrips.
- [x] Security audit tests validating the threat model checklist (encryption at rest, keyed hashing, rate limiting, no PII in logs, no third-party tracking).
- [x] All 77 tests pass.

## Phase 2: Content & Communication Layer
*Goal: Build the interface for organizers and participants.*
- [ ] Develop content hosting (flyers, descriptions, media) with encryption-at-rest.
- [ ] Create "Secure Communication Boards" (bulletins/comments) restricted by Key.

## Phase 3: Frontend & UX/UI Design
*Goal: Ensure the platform is intuitive and aesthetically compelling.*
- [ ] Develop a mobile-first responsive web application.
- [ ] Refine Security UI to ensure seamless user experience during key entry.

## Phase 4: Map & Navigation (Privacy-Preserving)
*Goal: Integrate open-source maps without third-party tracking.*
- [ ] Select open-source map tiles (e.g., OpenStreetMap, self-hosted).
- [ ] Implement basic routing/geofencing without third-party tracking.
- [ ] Link specific Keys to geographic coordinates or routes.

## Phase 5: Payment & Ticketing System
*Goal: Implement privacy-preserving financial transactions.*
- [ ] Research and integrate privacy-focused payment rails (e.g., Monero).
- [ ] Develop ticketing logic that generates a "ticket" upon successful payment.

## Cross-Cutting: Federation
*Goal: Support multi-instance key validation without a central registry.*
- [ ] Implement local-first resolution (partially done in `resolve_federation_prefix`).
- [ ] Explore DIDs for organizer identity.
- [ ] Define federated key validation protocol (opt-in, authenticated, minimal data).

---

## Technical Stack Notes
- **Language:** Python 3.11 (use `python3` on this machine).
- **Infrastructure:** Target Co-op Cloud / Self-hosted instances.
- **Maps:** OpenStreetMap (OSM) or similar.
- **Security Focus:** Minimal data retention, no third-party analytics, encryption at rest.

## Context for Future Sessions
*This section is updated as we progress to maintain continuity.*
- Current focus: Phase 1 - Core Architecture (security hardening) is **complete** (all 77 tests pass).
- Next: Phase 2 - Content & Communication Layer (content hosting, secure communication boards).
- Environment uses `python3` (not `python`).
- `KeyManager` accepts an optional shared `DatabaseHandler`; `Gateway` passes its own `db` to `KeyManager`.
- **Required environment variables:**
  - `GATEKEYP_MASTER_KEY`: Fernet-compatible master key for encryption-at-rest (fail-secure).
  - `GATEKEYP_HMAC_SECRET`: Per-instance secret for HMAC keyed hashing (fail-secure).
- **Test setup:** `pytest.ini` configures `pythonpath = . tests`; `tests/helpers.py` provides shared test constants.
- **Dependencies:** `cryptography`, `argon2-cffi`, `pytest`, `hypothesis`.
