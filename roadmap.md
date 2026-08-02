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

## Phase 1: Core Architecture (Security-Hardened)
*Goal: Harden key management, database schema, and API gateway.*

### Key Management
- [ ] Replace plain SHA-256 with HMAC-SHA256 (keyed by per-instance secret) or Argon2id for stored key verification.
- [ ] Add key rotation and revocation support.
- [ ] Enforce minimum key entropy at generation.

### Database
- [ ] Add `created_at`, `location_data` columns to schema.
- [ ] Add `key_content_links` join table (many-to-many key ↔ content mapping).
- [ ] Add encryption-at-rest for sensitive payloads (Fernet/AES-GCM with master key).
- [ ] Add federation fields (owner identifier prefix) to schema.

### Gateway
- [ ] Add rate limiting (per-IP and per-key) with exponential backoff.
- [ ] Harden input validation.
- [ ] Add structured audit logging (no PII).

### Tests
- [ ] Unit tests for negative/edge cases (invalid, expired, revoked keys; brute-force attempts; unauthorized content access).
- [ ] Integration tests for the full request flow.
- [ ] Security audit checklist passes (see `docs/threat_model.md`).

## Phase 2: Map & Navigation (Privacy-Preserving)
*Goal: Integrate open-source maps without third-party tracking.*
- [ ] Select open-source map tiles (e.g., OpenStreetMap, self-hosted).
- [ ] Implement basic routing/geofencing without third-party tracking.
- [ ] Link specific Keys to geographic coordinates or routes.

## Phase 3: Content & Communication Layer
*Goal: Build the interface for organizers and participants.*
- [ ] Develop content hosting (flyers, descriptions, media) with encryption-at-rest.
- [ ] Create "Secure Communication Boards" (bulletins/comments) restricted by Key.

## Phase 4: Payment & Ticketing System
*Goal: Implement privacy-preserving financial transactions.*
- [ ] Research and integrate privacy-focused payment rails (e.g., Monero).
- [ ] Develop ticketing logic that generates a "ticket" upon successful payment.

## Phase 5: Frontend & UX/UI Design
*Goal: Ensure the platform is intuitive and aesthetically compelling.*
- [ ] Develop a mobile-first responsive web application.
- [ ] Refine Security UI to ensure seamless user experience during key entry.

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
- Current focus: Phase 0 - Foundation & Hardening is **complete** (all 13 tests pass).
- Next: Phase 1 - Core Architecture (security hardening: HMAC/Argon2id key hashing, encryption at rest, rate limiting).
- Environment uses `python3` (not `python`).
- `KeyManager` accepts an optional shared `DatabaseHandler`; `Gateway` passes its own `db` to `KeyManager`.
