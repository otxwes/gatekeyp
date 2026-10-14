# Plan — Codebase cleanup & hygiene sweep

Scope approved by user (2026-10-13): **full sweep** — testing tooling, CI, security
posture, dead/redundant code. Includes the security behavior changes (per-IP rate
limiting, rate-limited writes, Argon2 for RSVP passphrases) and removal of all
verified-dead code.

Baseline (verified):
- `uv run pytest` → 309 passed, 34 e2e deselected, 1 StarletteDeprecationWarning
- `uv run ruff check src/ tests/` → clean
- `uv run ty check src/` → **FAILS** (8 `unresolved-import` RNS/LXMF in `lxmf_delivery.py`)
- `uv run pip-audit` → **FAILS** (11 vulns: `urllib3 2.7.0`→2.8.0, `virtualenv 21.7.1`→21.7.11/12/13)

## Status
- [x] Area A (testing): partial — see per-item
- [x] Area B (CI/container): done via subagent
- [x] Area C (security): C1 C2 C3 C4 done
- [x] Area D (dead code): D1 D2 D4 D8 done; D3 partial; D6/D7 pending
- [x] Area E (deps): E1 E2 done; E3 satisfied (argon2 used by RSVP)

---

## Area A — Testing framework (owner: main)

- [x] A1. Add pytest battery deps to `test` group: `pytest-cov`, `pytest-timeout`.
- [ ] A1b. (skip pytest-xdist — unit suite is sub-3s; env-mutation tests aren't parallel-safe)
- [x] A2. Add `[tool.coverage.run]`/`[tool.coverage.report]` scoped to `src/` (fail_under set
      after measuring).
- [x] A3. Add `Makefile coverage` target.
- [x] A4. `pytest.ini`: add `--strict-markers`, `--timeout`, `-ra`.
- [ ] A5. Project-wide Hypothesis profile in `tests/conftest.py` (CI deadline, derandomize,
      DB-backed examples).
- [ ] A6. Dedupe tests: `tests/helpers.py` vs `conftest.py`; unify import style; hoist shared
      fixtures; drop duplicated encryption/rate-limit tests.
- [ ] A7. Coverage-gap tests: `revoke_access_key_by_hash`, `get_public_view_by_slug`, DB
      migration machinery.
- [ ] A8. StarletteDeprecationWarning (httpx/httpx2) — decide ignore-vs-fix before enabling
      any `filterwarnings=error`.

## Area B — CI & container (subagent: done)

- [x] B1. Delete placeholder SLSA workflow.
- [x] B2. Add `.github/workflows/ci.yml` (lint/test/e2e/audit/docker-build).
- [x] B3. Add `.github/dependabot.yml`.
- [x] B4. (scheduled scan — fold cron into ci.yml if desired; optional)
- [x] B5. Dockerfile CMD → `uvicorn src.api.server:app --host 0.0.0.0`.
- [x] B6. compose: `/health` healthcheck + `GATEKEYP_DB_PATH`.
- [x] B7. Remove `requirements.txt`.

## Area C — Security code changes (owner: main)

- [x] C1. Per-IP access rate limiting (`/api/access` passes `request.client.host`).
- [x] C2. Rate-limit write routes (media/bulletin/comment/deletes) via dedicated `RateLimiter`.
- [x] C3. Argon2id for RSVP passphrases (OWASP params) + legacy-HMAC fallback.
- [x] C4. Fix `.env.example` Fernet key snippet (+ stale DB-path default).
- [x] C5. (extra) Fixed `set_flyer` `asset_id` annotation bug ty caught.

## Area D — Dead code & N+1

- [x] D1. Removed dead `Gateway` content layer (8 methods + `_handle_content_error`);
      updated `test_content_manager.py` (routes already covered at HTTP level).
- [x] D2. Removed dead `KeyManager` `verify_key`/`rotate_key`/argon2 helpers + dead constants;
      updated `test_key_manager.py`.
- [~] D3. Removed `delete_rsvps_for_event` (zero callers). KEPT `is_key_revoked` /
      `get_keys_for_content` (test-only helpers) and `get_parent_event` (used); noting as
      intentionally-kept to avoid churn.
- [x] D4. Removed `LiteRateLimitError`, `RsvpRateLimitError`.
- [x] D5. Removed dead JS/CSS (subagent).
- [x] D6. N+1 fixed in `list_access_keys`/`decommission_event` via new
      `list_access_keys_for_event` join. RSVP-list per-row `get_key` left as minor micro-opt
      (organizer-only path; deferred to avoid churn).
- [ ] D7. Dedupe `_validate_text`/identical rate-limiters/`_fmt_*` (low-value; DEFERRED —
      security-relevant limiter duplication is intentional per inline comments).
- [x] D8. Remove `vendor/` third-party tree.

## Area E — Dependency & supply-chain (owner: main)

- [x] E1. Bumped `urllib3`/`virtualenv`; `pip-audit` clean.
- [x] E2. Fixed `make typecheck` (`set_flyer` typing + ty `allowed-unresolved-imports`).
- [x] E3. `argon2-cffi` now genuinely used (RSVP passphrases), stays in runtime deps.

## Area A — Testing framework (final)

- [x] A1/A2/A3. pytest-cov + pytest-timeout deps, `[tool.coverage]` config, `make coverage`.
- [x] A4. pytest.ini: `--strict-markers`, `--timeout=300`, `-ra`, curated warning filter.
- [x] A5. Project-wide Hypothesis profile (2s deadline, derandomize) in conftest.
- [~] A6. `helpers.py` made canonical; `conftest.py` imports it; import style standardized.
      Deeper fixture-hoisting (`_FakeClock`, app/client/limiter fixtures) DEFERRED.
- [x] A7. Coverage-gap tests: `revoke_access_key_by_hash` (+ wrong-event), `get_public_view_by_slug`
      (+ unknown), DB schema-migration test.
- [x] A8. Suppressed the third-party httpx/httpx2 StarletteDeprecationWarning (not ours).

## Final verification (all real output)

- `uv run ruff check src/ tests/` → All checks passed
- `uv run ty check src/` → All checks passed  (was failing: 8 diagnostics)
- `uv run pytest` → 302 passed, 34 e2e deselected  (baseline was 309; -7 removed dead-code tests,
  +new coverage-gap tests)
- `uv run pip-audit` → No known vulnerabilities found  (was failing: 11 vulns)
- `uv run pytest --cov=src` → 84.8% (gate: 75%) reached
- `uv run ruff format --check src/ tests/` → clean
- `uv run pytest tests/e2e -m e2e` → 34 passed (server boots under all changes)

### Deferred / optional (documented, not blocking)
- Deeper test fixture hoisting & remaining minor dedup (D7, A6 details)
- Scheduled dependabot-style vuln scan job cron (B4)
- RSVP list per-row `get_key` micro-optimization
- Verify `docker build`/`docker run` in a real Docker daemon (unavailable in this env; the
  `docker-build` CI job is the authoritative final check)
