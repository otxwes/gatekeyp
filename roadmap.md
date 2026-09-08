# Roadmap: gatekeyp

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

## Phase 2: Content & Communication Layer ✅
*Goal: Build the interface for organizers and participants.*

### Content Hosting
- [x] Implement `ContentManager` for media assets (flyers, images, documents) with encryption-at-rest.
- [x] MIME-type validation and size limits for media uploads (10 MB max).
- [x] Key-gated access to all content (valid key required for upload/retrieval).
- [x] Media asset CRUD (upload, get, list, delete).

### Secure Communication Boards
- [x] Implement bulletins (communication board posts) with encrypted bodies.
- [x] Implement threaded comments with parent-comment support.
- [x] Key-gated access to bulletins and comments.
- [x] Bulletin CRUD (create, get, list, update, delete).
- [x] Comment posting, listing, and deletion.

### Event Lifecycle Management
- [x] Implement `EventLifecycleManager` for end-to-end event orchestration.
- [x] Event creation with master key generation (365-day default lifetime).
- [x] Attendee access key generation (30-day default lifetime), listing, and revocation.
- [x] Content block management (descriptions, schedules, etc.).
- [x] Event decommissioning (revokes master key and all access keys).

### FastAPI Server & Web UI
- [x] Implement FastAPI HTTP server with RESTful endpoints for all features.
- [x] Static web UI served from the same process.
- [x] Mobile-first, privacy-preserving frontend (no third-party tracking).
- [x] CORS support for development.
- [x] All 136 tests pass.

## Phase 3: Frontend & UX/UI Design
*Goal: Ensure the platform is intuitive and aesthetically compelling.*
- [x] Refine Security UI to ensure seamless user experience during key entry.
- [x] Enhance web UI with additional event management features.
- [x] Add responsive design polish and accessibility improvements.

Delivered as `web/app.js` — a hash-routed, dependency-free SPA that drives the
repaired `web/index.html` and the Phase-3 editorial design in `web/style.css`:
- Organizer desk: create / open events (one-time master-key modal), then a
  four-tab workspace — Content, Bulletin board, Media, Access keys — plus a header
  Decommission action, framed by a master-key banner.
- Attendee door: unlock an invite with an access key, then read content, post
  on the bulletin board, leave comments, and view media — no account needed.
- Session keys live only in `sessionStorage` (dropped when the tab closes);
  raw keys are shown exactly once in a modal with copy-to-clipboard.
- Toasts, confirm modals, loading + empty states, light/dark theme toggle
  (respects `prefers-color-scheme`), full keyboard support, reduced motion.

## Phase 3.5: UX & Visual Design Iteration (Are.na-Minimal)
*Goal: Take the SPA from "functional" to a deliberate, handcrafted identity — Are.na-informed minimal & sleek: quiet editorial, monochrome paper & ink (Monochrome Edition, v1 — the warm/vermilion palette is retired), strong serif display type, generous air, hairline borders, one ink accent, texture instead of color, calm motion. This track *tightens* the Phase-3 editorial root rather than rebuilding it.*

- [x] Write `docs/design_system.md` — type pairing/scale/leading, light & dark theme tokens, spacing rhythm, radii/shadows, motion language (durations/easing + `prefers-reduced-motion`), and explicit "no generic generated-look" rules.
- [x] Typography + grid pass on `web/style.css` — tighten scale/measure/leading, impose a real grid on the desk & door surfaces, and tame the current "vibe-coded" looseness.
- [x] Component + state unification — buttons/cards/badges/toasts/modals/empty/loading/error/focus/disabled consistent across both themes.
- [x] Motion & micro-interactions — route/tab transitions, modal & toast entrances, button feedback (keep reduced-motion support).
- [x] Build a small in-house motif/ornament set (stamps, hatches, key-art) reused by the UI and the Phase-3.6 invite cards. — **Done 2026-08-30.** Monochrome texture language (`web/style.css` §17): `--hatch-soft/-fill/-strong` fills, `.voided` composite + `--dot` paper tooth; wired into master banner, empty states, decommission modal, state badges, and toasts. Primitive classes (`hatch-*`, `.voided`) are the vocabulary Phase 3.6 invite cards build on. Documented as design-system §12.
- [x] Accessibility + responsive review (WCAG AA in both themes, 44px targets) and a light/dark x mobile/desktop x owner/attendee QA matrix. — **Done 2026-08-30.** Grayscale ramp verified AA/AAA (ink 18.9:1 light / 18.0:1 dark; faint 5.3:1 / 7.0:1; chips ≥ 8:1 worst case); icon-btn raised 38→44px, tabs ≥ 40px; non-color status glyphs (`⚠`/`✓`) added to form notes; full matrix in `docs/qa_matrix.md`.

## Phase 3.6: Steganographic Invite Keys (Key-Distribution UX)
*Goal: Replace the "copy/paste a hex blob" moment with a beautiful, shareable invite artifact that *contains* the key — dropped at the attendee door instead of typed. Server surface unchanged (HMAC + expiry + revocation); keys never leave a client tab.*
*Sequencing: 3.5 founds the design system the invite cards are drawn on; 3.6 follows and may run in parallel with Phase 4 (Map).*

- [x] `web/stego.js` — zero-dependency PNG low-bit codec: manual PNG parse + `CompressionStream`/`DecompressionStream` inflate, LSB/RGB payload with checksum + repetition for robustness (avoids canvas colour-management corruption). — **Done 2026-08-30.** Full codec (`embed`/`extract`/payload/QR helpers) mirrored byte-for-byte in `tests/stego_ref.py`; golden vectors + the JXA (JavaScriptCore) cross-check pin JS↔Python agreement, and caught two real bugs during development (missing IIFE invocation; float64-`SEED` imprecision).
- [x] `web/invite_card.js` — canvas invite-card renderer (event title/date/location + Phase-3.5 ornament + QR fallback); embeds event id + access key. — **Done 2026-08-30.** Portrait 800×1200 paper-and-ink card (keyhole motif, hatch/keyline bands, dotted tooth, serif display type) + stego download.
- [x] Vendor MIT `qrcode-generator` (single-file, ~10 KB) as the "still scannable after social re-encode" fallback printed on the card. — **Done 2026-08-30.** `web/vendor/qrcode-generator.js` + LICENSE.
- [x] Organizer UX — "Download invite card" beside the existing copy-key flow in the Access-keys tab. — **Done 2026-08-30.** "Also make an invite card" in the one-shot key modal + per-row "Card" action (re-enters the raw key — keys are shown once by design and never stored).
- [x] Attendee UX — "drop or paste your invite" zone above the unlock form on the door; decode locally, auto-fill event id + access key (manual entry always works). — **Done 2026-08-30.** Drop / paste image / paste `gkp:` text / choose file; auto-fills the existing form.
- [x] Resilience batch — QR *decode* at the door (photos / re-encodes), honest per-kind rejection, share guidance. — **Done 2026-08-30.** Vendored `jsQR` (Apache-2.0, 256 KB UMD) + LICENSE; `web/door_qr.js` (canvas-capped, capped 1600 px, local decode); `classifyInvite`/`inviteRejectReason` in `stego.js` mirrored in `stego_ref.py` and pinned by the JXA cross-check; the door rejects with the fix ("scan it or share the original PNG") instead of a generic error; card modals say "send as a file, not a photo". +2 tests (166 total).
- [x] Docs — `docs/steganography_invites.md` + threat-model note (PNG-only / no-re-encode warning; opsec value vs. QR; payload = event id + access key; parity with expiry + revocation; no new server surface). — **Done 2026-08-30.**
- [x] Tests — Hypothesis encode<->decode round-trips, decode of a known fixture, E2E via the demo server. — **Done 2026-08-30.** 21 new tests (`tests/test_stego_invites.py`), committed fixture, JXA cross-check; live-server browser E2E is the final pass of this phase.

## Phase 3.7: Custom Card Covers (Client-Side)
*Goal: Let organizers personalize the invite card's top band — preset monochrome patterns by default, or their own image drawn cover-fit. Purely client-side (consistent with the keys-never-leave-tab design); the hidden key and the printed QR are untouched.*

- [x] Cover engine in `web/invite_card.js` — `coverFit` (object-fit:cover crop math), `drawPreset` (hatch / keyline / dots / keyhole motifs), `drawCoverBand`, `renderCover` (picker swatches), async image-cover loading; `render()` gained a `scale` option and draws the cover band (704×240) above the title. — **Done 2026-08-30.** Title/rule/meta shifted down; QR + bottom rail untouched (no tests pin the card geometry, so the shift was safe).
- [x] Cover picker in `web/app.js` — shared `openCardCoverModal` (preset chips with live canvas swatches + "Own image…" upload + live 200×300 card preview), routed from both the one-shot card button and the per-row "Card" action. — **Done 2026-08-30.**
- [x] Tests — `tests/card_ref.py` oracle + `tests/test_invite_card_cover.py` (golden vectors, Hypothesis object-fit:cover properties, JS↔oracle preset-id lock-step); the JXA cross-check now also loads `invite_card.js` and pins `coverFit` vs Python; E2E static needle. — **Done 2026-08-30.**

## Phase A: Embeddable Pivot — Ephemeral ("Lite") Events ✅
*Goal: First step of the embeddable pivot — let anyone fly a short-lived, no-account event: a public flyer page with Open Graph tags for social sharing, key-gated details behind it, and a self-wipe deadline. Unauthenticated creation funnel with a hard rate limit.*
*Full engineering detail: `docs/project_memory.md` → "Phase A: ephemeral ('lite') events landed" (2026-09-08).*

- [x] Schema — `events` gained `mode` + `expires_at` (additive `_ensure_column` migration so pre-existing DBs upgrade on open; verified against a backup copy before touching `keys.db`); new `event_tombstones` table; `wipe_event()` single-transaction wipe of event + blocks + media + links + now-orphaned keys, leaving an honest tombstone. — **Done 2026-09-08.**
- [x] `src/ephemeral/` — `EphemeralService` (TTL 1–336 h, fail-closed expiry check, injectable clock, `sweep_expired()`, dedicated fixed-window rate limiter) plus routes: `POST /api/lite/events`, `GET /i/{event_id}` OG page, public flyer bytes (`nosniff`), keyed attendee view. Master keys get ceil(TTL/24)+1 days so they outlive the event. — **Done 2026-09-08.**
- [x] Server profiles — `create_app(profile=…)`, `GATEKEYP_PROFILE` (full|lite; unknown → ValueError); the lite profile mounts only funnel routes + `/health` + static UI; startup sweep wipes events whose TTL elapsed while the process was down. `make serve-lite` added. — **Done 2026-09-08.**
- [x] Frontend — `#/flyer` creation funnel (title; gated description/when/where; optional public flyer upload; TTL) → one-shot master key with copyable share/organizer links; `#/e/{event_id}` attendee page with `?k=` unlock and an honest "Event ended" state. — **Done 2026-09-08.**
- [x] Tests — 36 in `tests/test_ephemeral.py` (schema migration incl. a legacy-DB fixture, wipe semantics incl. shared-key preservation, views/expiry with an injectable clock, HTTP surface incl. OG-page leak checks and 429 on the sixth creation) + `TestEphemeralSecurityAudit` (gated content + flyer encrypted at rest; wipe leaves no plaintext in any table; tombstone records nothing sensitive). Suite: 217 passing. — **Done 2026-09-08.**
- [x] Live QA (browser, lite profile on :8775) — funnel fill + flyer upload → one-shot master key panel; OG page shows title + flyer + wipe deadline and **no gated content**; `?k=` attendee unlock renders when/where + flyer; expired OG page → "Event ended" tombstone; keyed attendee page → "Event ended — All data for this event was wiped."; `sweep_expired()` wiped event + media + blocks from the live DB, leaving the tombstone only. — **Done 2026-09-08.**
- [ ] Known cosmetic gap: no favicon route — `GET /favicon.ico` 404s on the OG page (console noise only, nothing functional).
- [ ] Phase A+ (next, proposed — not yet scoped): embeddable surface — `<script>`/iframe widget so the flyer can live anywhere, richer OG/Twitter card tags, embed-ready share links; scope the embed-hosting boundary in `docs/threat_model.md` before building.

## Phase 4: Map & Navigation (Privacy-Preserving)
*Goal: Integrate open-source maps without third-party tracking.*
- [ ] Select open-source map tiles (e.g., OpenStreetMap, self-hosted).
- [ ] Implement basic routing/geofencing without third-party tracking.
- [ ] Link specific Keys to geographic coordinates or routes.

## Phase 5: Payment & Ticketing System
*Goal: Implement privacy-preserving financial transactions.*
- [ ] Research and integrate privacy-focused payment rails (e.g., Monero).
- [ ] Develop ticketing logic that generates a "ticket" upon successful payment.

## Phase 6: Local Situation Awareness (Public Safety Radio + AI)
*Goal: A privacy-preserving "situation layer" for an event — real-time, event-adjacent awareness for organizers & attendees, derived from public-safety radio and interpreted locally by an open ML pipeline.*

### Research findings (2026-08) — see `docs/research_notes/06_scanner_intel.md` for sources
- **Broadcastify has NO public live-audio API.** The Feed Catalog API (v1.3) is *metadata-only* and licensee-gated ("currently not issuing additional licenses"); the Feed Owner API is feed-providers-only; the Calls Upload API is *push-only* (you upload clips to them). Live streams are not consumable programmatically.
- **Sanctioned bulk audio:** Broadcastify archives via RadioReference **premium** (fee), licensed **CC BY 3.0** ("Audio Provided by Broadcastify") — suited to post-event analysis/training, not real-time.
- **The viable real-time path is self-production:** RTL-SDR/AirSpy + **trunk-recorder** (GPL — the open-source engine that actually supplies Broadcastify & OpenMHz feeds) decodes per-talkgroup audio + JSON metadata locally, surfaced via **Rdio Scanner / Trunk Player** or a small local `src/intel/` service. Fully self-hosted — fits the project's local-first, no-third-party-tracking ethos, with zero API-key/ToS dependency.
- **Fallback feed source:** **OpenMHz** (free JSON-call API, by the same author as trunk-recorder) where a system is already monitored; verify availability at build time.
- **Dominant risk = encryption:** growing P25-AES adoption means many metros' police audio simply does not exist for anyone (Broadcastify, OpenMHz, or self-hosted). Documented example: OpenMHz's origin city (DC) broadcasts Fire/EMS/City on the open system, but DC PD is encrypted. A per-metro pre-flight check is mandatory.
- **Legal/ethical baseline:** receiving unencrypted public-safety radio is lawful federally; some states restrict scanners (in-vehicle use, "in furtherance of a crime"). Never decrypt or circumvent encryption. Broadcastify's own LE ToS restricts feeds to *routine dispatch* channels (no tactical/NCIC/records).

### Phase 6 work
- [x] Write `docs/research_notes/06_scanner_intel.md` (seeded from 2026-08 research; expand and add per-metro pre-flight at build time).
- [ ] **Path A (recommended): self-hosted SDR capture** (near-venue or venue receiver). RTL-SDR/AirSpy + `trunk-recorder` -> per-talkgroup audio clips + JSON call records (talkgroup/site/frequency/source); expose via Rdio Scanner or a minimal local `src/intel/` service.
- [ ] **Path B: OpenMHz API** ingestion where coverage already exists (zero hardware), flagged per-metro availability.
- [ ] **Path C: Broadcastify** — Feed Catalog API (metadata) for audience discovery/monitoring + premium archives (CC-BY) for post-event analysis & model training. Not real-time.
- [ ] AI interpretation pipeline (local-first): per-clip STT (`faster-whisper` / `vosk` local; cloud optional), talkgroup-aware structuring (dispatch = the permissible channel; filter routine traffic), incident-type + location extraction, geofence/alerting tied to Phase-4 map coordinates, LLM "situation brief" for organizers/attendees; **no raw audio retained by default**.
- [ ] Ethics & privacy position: monitoring agencies, not attendees; civilian PII/medical redaction; transparent labeling; opt-in visibility; publish the position in `docs/threat_model.md`.
- [ ] Module boundaries: separate `src/intel/` service + ephemeral/encrypted DB tables; no third-party analytics; consistent with the federated/self-hosted architecture.
- [ ] Open decisions to revisit: target metro(s)? real-time vs post-event only? local vs cloud ML? hardware/cloud budget?

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
- Current focus: Phase 3 - Frontend & UX/UI Design is **complete** (full SPA in `web/app.js`; redesign in `web/style.css`; markup repaired in `web/index.html`). Phase 3.5 - UX & Visual Design Iteration is **complete** (Monochrome Edition: B&W palette + motif set §19, a11y + QA matrix). Phase 3.6 - Steganographic Invite Keys is **complete** (codec + card + QR encode/fallback + organizer/attendee UX + door QR decode + honest rejection + share guidance + docs + tests). Phase 3.7 - Custom Card Covers is **complete** (preset monochrome covers + own-image upload drawn cover-fit; client-side only). Phase A - Ephemeral ("Lite") Events (embeddable pivot, first step) is **complete** (`src/ephemeral/`, `#/flyer` funnel, `#/e/{id}` attendee door, self-wipe + tombstones, `GATEKEYP_PROFILE=lite` server profile; live QA on 2026-09-08 passed end-to-end).
- Next: Phase A+ embeddable surface (iframe/script widget, richer OG cards — proposed, needs scoping + threat-model boundary) and/or Phase 4 - Map & Navigation. Invite-card art reuses the Phase-3.5 motif primitives (`--hatch-*`, `.voided`) — design-system §12.
- Test suite: 217 tests passing (`arch -x86_64 python -m pytest -q`; the venv's `cryptography` wheel is x86_64 on Apple Silicon — or `uv run pytest`, which handles the interpreter). Plus `python -m tests.jxa_stego_check` for the JS↔Python codec agreement (now incl. `coverFit` pins), and `python -m tests.stego_ref --write-fixture` to regenerate the invite-card fixture.
- Commit D landed (`5c57b4b`) — custom card covers complete and pushed; the local dev server (`src.api.server`) is live on `127.0.0.1:8000` and serves `web/` from disk (web/* edits go live per-request, no restart; `src/*` changes need a restart).
- Environment uses `python3` (not `python`).
- `KeyManager` accepts an optional shared `DatabaseHandler`; `Gateway` passes its own `db` to `KeyManager`.
- `ContentManager` requires shared `DatabaseHandler` and `KeyManager` instances.
- `EventLifecycleManager` requires shared `DatabaseHandler`, `KeyManager`, and `ContentManager` instances.
- FastAPI server (`src/api/server.py`) wires all services together and serves the static web UI.
- **Required environment variables:**
  - `GATEKEYP_MASTER_KEY`: Fernet-compatible master key for encryption-at-rest (fail-secure).
  - `GATEKEYP_HMAC_SECRET`: Per-instance secret for HMAC keyed hashing (fail-secure).
- **Test setup:** `pytest.ini` configures `pythonpath = . tests`; `tests/helpers.py` provides shared test constants.
- **Dependencies:** `cryptography`, `argon2-cffi`, `fastapi`, `python-multipart`, `uvicorn`, `pytest`, `hypothesis`.
