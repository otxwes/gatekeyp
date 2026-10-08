# Implementation Plan — Persistent Playwright UAT Suite for gatekeyp

## Overview
Build a persistent, repeatable Playwright (Python + pytest) end-to-end suite at
`tests/e2e/` that drives the real browser UI across **every user path** in the app
(organizer desk, attendee join/unlock, RSVP funnel, flyer/lite funnel, key lifecycle,
session behavior) against an **isolated throwaway database**, asserting on rendered DOM
text with console/network watchers on every page, so wiring bugs like the
"content block never rendered attendee-side" class are caught automatically.

Investigation findings that shape this plan:
- **Views** in `web/index.html` / `web/app.js` (router `route()` ~line 353):
  `#/` home, `#/organize` (workspace tabs: content, bulletins, media, keys, rsvps —
  `WS_LOADERS` at ~554), `#/join` (drop zone `#key-drop`, file input `#key-drop-file`,
  paste handler ~1600–1676), `#/flyer` (ephemeral event creator, `#flyer-form`),
  `#/e/{id}?k={key}` lite event (`renderLiteEvent` ~2153), `#/rsvp/{eventId}` funnel.
- **Invite transport is a stego PNG**: keys tab mints invite cards; attendee unlocks
  by dropping/pasting the card (or via lite manual-key form). Playwright can download
  the generated PNG and re-feed it via `set_input_files` — automatable headless.
- **DB isolation**: `DatabaseHandler.__init__` (`src/db/database_handler.py:45`)
  defaults `db_path="keys.db"` (a relative path) — the plan adds a one-line
  `GATEKEYP_DB_PATH` env override so the E2E server boots on a temp-dir DB with the
  deterministic `.env.dev` secrets.
- **Port isolation**: `GATEKEYP_PORT` env is already honoured (`src/api/server.py:488`)
  — E2E server runs on **:8777**, never the dev :8000.
- **Clipboard copy** in keys tab works headless via
  `context.grant_permissions(["clipboard-read", "clipboard-write"])` (Chromium).

## Types
- `ScenarioError(RuntimeError)` — raised with scenario name + cause by watchers and
  failed assertions; message surfaced by pytest.
- `Artifacts` (dataclass in `tests/e2e/conftest.py`) — base URL (:8777), temp DB path,
  organizer key; passed to every test via fixture.
- Role-split fixtures: `"organizer"` / `"attendee"` browser contexts per test.

## Files
- **`src/db/database_handler.py`** (modify, minimal): in `__init__`, resolve
  `db_path = os.environ.get("GATEKEYP_DB_PATH", "keys.db")` when caller passes none.
  Enables per-run isolated DB; no schema/behavior change. (+ unit test.)
- **`pyproject.toml`** (modify): add `playwright`, `pytest-playwright` to the
  `[dependency-groups] test` group (matches existing layout).
- **`tests/e2e/conftest.py`** (new): session-scoped server/DB fixtures (below).
- **`tests/e2e/helpers.py`** (new): `ConsoleWatcher`, `OrganizerPage`, `AttendeePage`,
  screenshot util (`/tmp/gkp-e2e/<scenario>/<step>.png`).
- **`tests/e2e/test_organizer_flows.py`** (new): scenarios A1–A11.
- **`tests/e2e/test_attendee_flows.py`** (new): scenarios B1–B10.
- **`tests/e2e/test_lite_flows.py`** (new): flyer creation end-to-end + lite C1–C5.
- **`tests/e2e/test_rsvp_interlock.py`** (new): organizer↔attendee closed loop (D1–D8).
- **`tests/conftest.py`** (modify): register `e2e` marker; default sweep stays
  unchanged — E2E runs via explicit `uv run pytest tests/e2e/`.
- Optional config: reuse `scripts/with_server.py` pattern from the webapp-testing
  skill for server lifecycle in `conftest.py`.

## Functions
New (all in `tests/e2e/`):
- `conftest.py::server()` — session fixture; boots
  `GATEKEYP_DB_PATH=<tmp>/keys.db GATEKEYP_PORT=8777 [+ .env.dev secrets]
  uv run python -m src.api.server`, waits on `GET /health`; teardown terminates the
  process and deletes the temp dir (project rule: no lingering processes).
- `conftest.py::organizer_context()` / `attendee_context()` — fresh isolated contexts
  (own localStorage/sessionStorage).
- `helpers.py::OrganizerPage.create_event(title, description)` — drives the
  `#create-event-form` on `#/organize`.
- `OrganizerPage.add_content_block(content_type, payload)` / `.delete_content_block`
  — workspace Content tab.
- `OrganizerPage.post_bulletin(body)` / `.comment(...)` / `.delete_bulletin(...)`
  — Bulletin tab.
- `OrganizerPage.upload_media(png_path)` / `.delete_media()` — Media tab.
- `OrganizerPage.mint_key()` — Keys tab; downloads invite PNG to tmp; reads invite
  link text (clipboard granted); returns `(png_path, invite_text)`.
- `OrganizerPage.revoke_key(label)`; `.set_rsvp_auto_approve(on)`; `.approve_rsvp(name)`
  / `.deny_rsvp(name)` — asserts quoted italic `kd-msg` message matches submission.
- `OrganizerPage.decommission_event()` — confirm modal + degraded states.
- Playwright docs (fetched): role/text locators + web-first `expect()`, per-test
- `helpers.py::AttendeePage.drop_invite(png_path)` — join file-input path.
- `AttendeePage.paste_invite(text)` — document paste-handler path.
- `AttendeePage.enter_key_in_lite(event_id, key)` — `#/e/…` manual form.
- `AttendeePage.submit_rsvp(name, message, oversize=False)` — RSVP funnel incl. the
  512-char cap edge.
- `AttendeePage.expect_details_card()`, `.expect_bulletin(text)`, `.expect_media(n)` —
  web-first DOM assertions on the event page.
- `helpers.py::ConsoleWatcher.attach(page)` / `.assert_clean(reason)` — collects
  console errors, pageerrors, non-2xx/3xx responses; fails cumulatively.

## Classes

**Scenario matrix** (the behavior contract each test asserts):
- **A. Organizer (11)**: (A1) bootstrap workspace, (A2) create event, (A3) add each
  block type, (A4) delete block, (A5) upload+delete media, (A6) bulletin
  post/comment/delete-comment/delete-bulletin, (A7) mint key → PNG + link, (A8)
  invite link copy/flyer text, (A9) revoke key listed, (A10) decommission, (A11)
  reload persistence + End-session discard toast.
- **B. Attendee (10)**: (B1) unlock via dropped invite PNG, (B2) unlock via pasted
  link text, (B3) unlock via lite manual-key form, (B4) full event-page sweep —
  **every organizer artifact surfaces attendee-side** (content blocks in the "Event
  details" card, bulletin board, media thumbs — the generic regression harness for
  the wiring-bug class), (B5) block added post-unlock visible at fresh unlock, (B6)
  refresh keeps session intact, (B7) End session → clean re-unlock, (B8) revoked-key
  rejection message, (B9) malformed-key input validation, (B10) rate-limit friendly
  message (no blank screen).
- **C. Flyer/Lite (5)**: (C1) flyer form → ephemeral event → lite URL unlock shows
  flyer image + when/where, (C2) missing `k` → fallback key form, (C3) wrong key
  error copy, (C4) expired/wiped event message, (C5) no-id empty state.
- **D. RSVP interlock (8)**: (D1) auto-approve ON → submit (name + "Message to the
  organizer", emoji, 512-cap edge) → instant event page incl. details card, (D2)
  auto-approve OFF → pending page, (D3) organizer queue shows quoted italic message,
  (D4) approve → "Open the event now" → full event page with blocks, (D5) deny →
  denial view, (D6) denied key later rejected at door, (D7) settings round trip,
  (D8) duplicate decide handled kindly.

## Implementation Order
1. `GATEKEYP_DB_PATH` override in `src/db/database_handler.py` (+ unit test).
2. Deps: `uv add --group test playwright pytest-playwright`; then
   `uv run playwright install chromium`.
3. `tests/e2e/conftest.py` — isolated server on :8777, health-wait, teardown kill —
   plus a smoke test proving boot and `/health`.
4. `tests/e2e/helpers.py` — watchers, page objects, screenshots, marker plumbing.
5. Scenario files in regression-value order: attendee flows (incl. content-block
   regression) → RSVP interlock → organizer flows → lite/flyer → mobile pass.
6. Fix any product bugs found; each fix gains its own regression scenario; re-run.
7. Final gates: full e2e run, unit sweep still green, ruff, ty; cleanup audit
   (no lingering servers/browsers, temp dirs removed).
- `ConsoleWatcher` (new) — `attach(page)`, `assert_clean(reason)`; only a favicon-404
  is ignored by default.
- `OrganizerPage` / `AttendeePage` (new) — composition over `page` + Playwright
  `expect`; no shared base class needed.

## Dependencies
- Add to test group: `playwright`, `pytest-playwright`.
- One-time `uv run playwright install chromium` (headless Chromium only).
- No runtime deps added; no third-party network calls in app code.

## Testing
- **~34 scenarios**, each isolated (fresh contexts; unique event ids; DB per session).
- Every scenario: `assert_clean()` (zero unexpected console errors/pageerrors/4xx-5xx
  outside deliberately-negative cases), screenshots per step, `expect()` on visible
  text. Mobile spot-check: B1/B4/B6/D1 under iPhone-13 viewport emulation.
- Run: `uv run pytest tests/e2e/`. Default unit sweep (`uv run pytest`, 303 tests)
  unchanged. Post-fix gates: ruff check+format, both sweeps, `uv run ty check src/`.
  isolation, `pytest-playwright` plugin, console/pageerror/response watchers,
  trace-on-failure.
