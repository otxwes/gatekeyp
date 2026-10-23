# Plan — Invite-card clarifying copy + organizer name for guests

Scope approved by user (2026-10-14), based on Slack feedback from a tester
(Jesse) about the Cellar app. Two of the five feedback items are in scope now;
the other three (organizer guest-ID, anti-impersonation, selfie verification)
are deferred while the user thinks them through.

## Agreed scope

**Item 1 — Invite-card clarifying copy**
Every surface that asks an *attendee* to download/make their invite card gets
one terse line clarifying that the card is what identifies them and gets their
request approved. Primary surface: the RSVP-result page (the flow the tester
screened — submit an RSVP, then asked to make/download the invite card) and the
card-cover modal opened from it.
- Design decision (user-approved): this explicitly overrides the repo's §3.4
  "de-caption" rule (no helper prose) for these specific lines. Keep each copy
  addition to a single terse sentence so it stays within the stripped aesthetic.

**Item 2 — Organizer name for guests**
Add an optional `organizer_name` (default blank) to events so guests know who
runs the event.
- Guest surfaces: the public RSVP request page and the unlocked attendee event
  page show the organizer name.
- `organizer_name` is **optional** at creation (default blank) per user choice.

## Files to touch

- `src/db/database_handler.py` — add `organizer_name TEXT` column to `events`
  via `_ensure_column` (additive migration pattern, same as prior phases);
  read/write it in `create_event` and event-detail rows.
- `src/api/server.py` — `CreateEventRequest` gains optional `organizer_name`;
  pass through on create. Ensure event-detail/RSVP view response includes it.
- `src/rsvp/service.py` — `get_public_view` / `get_public_view_by_slug` include
  `organizer_name`.
- `web/app.js` —
  - Item 2: add an "Organizer" name field to the event-create form (optional),
    send it in the create POST, store on the `org` object.
  - Item 2: render organizer name on the RSVP request page (`renderRsvp`) and
    the unlocked attendee page (`renderEventPage`).
  - Item 1: add the terse clarifying line to the RSVP-result page
    (`showRsvpResult`) and to the card-cover modal (`openCardCoverModal`) for
    the attendee-fresh path.
- `tests/` — cover: schema migration adds the column; creation stores
  `organizer_name`; event-detail + public RSVP view expose it; organizer name
  renders on RSVP + attendee pages; clarifying copy present on the result page
  / card modal. Follow existing test-file conventions (e.g. an organizer-name
  test alongside the ephemeral/rsvp/view tests).
- `docs/design_system.md` — record the scoped §3.4 exception for this copy
  (optional, one line) so the carve-out is documented.

## Tasks

- [x] T1. Schema: `_ensure_column("events", "organizer_name", "TEXT")` +
      `add_event` stores/reads it (`_EVENT_ORGANIZER_NAME_MIN_COLS` guard).
- [x] T2. API: optional `organizer_name` on `CreateEventRequest`; pass-through;
      include in event-detail + RSVP public view.
- [x] T3. Web (create): optional Organizer field in create form + POST + org
      object.
- [x] T4. Web (render): organizer name on RSVP request page + attendee event
      page.
- [x] T5. Web (copy): terse clarifying line on RSVP-result page + attendee card
      modal.
- [x] T6. Tests for all of the above; `uv run pytest` + `uv run ruff check src/ tests/`
      pass.

## Status: DONE (2026-10-14)

## Round 2 (2026-10-15): mobile UX from iPhone testing

Approved direction (user, in chat):
- **R2a (done, commit `b732d05`)**: "Save to Photos" is the first action in the
  card modal (above "Download to Files"); bottom confirm row dropped when
  share-capable; `openModal` supports `confirmText: null`.
- **R2b (this section)**: the RSVP funnel shows the event flyer in the request
  form, and the flyer is a cover option when the attendee makes their invite
  card. Standard-event flyers become publicly fetchable via a new no-key route
  (modeled on the lite public flyer route); threat-model note required.

### R2b tasks — DONE (implemented by subagent ses_ec22108a1ffeduLRJ3hjman0DV, which
### completed the work but its final report was lost to a provider error; verified
### in the main session 2026-10-15 before commit)
- [x] T1. `src/rsvp/service.py` `get_public_view`: include `flyer_asset_id`.
- [x] T2. `src/rsvp/routes.py`: `GET /api/events/{event_id}/rsvp/flyer` (no
      auth): 404 unknown event, 410 ended, 404 no flyer; serve decrypted bytes
      (inline, Cache-Control public max-age=86400, ETag, nosniff) modeled on
      the lite route (`src/ephemeral/routes.py` get_lite_flyer).
- [x] T3. `web/app.js`: renderRsvp renders the flyer image under the lede
      (class `event-flyer`, referrerpolicy no-referrer); attendee card-modal
      path resolves the flyer from the public route (`card.flyerAssetId` set at
      the showRsvpResult call site) so the Flyer cover chip appears.
- [x] T4. Tests: route (200/410/404s, headers), public view flyer id, e2e
      (flyer on request page + Flyer chip in the rsvp card modal).
- [x] T5. `docs/threat_model.md` note: funnel flyers are public (consistent
      with title/description already public on the funnel).
- [x] T6. Verify: pytest 315 passed + e2e 40 passed + ruff clean + JXA-OK +
      node --check OK (real output, run before commit).

Verified (real output, run in main checkout):
- `uv run pytest` → 310 passed, 34 deselected
- `uv run ruff check src/ tests/` → clean
- `uv run ty check src/` → clean
- `node --check web/app.js` → JS valid

Implemented by subagent (ses_ec2fc8a20ffe1DO8rMYDIINhY5). Note: the plan's
"create_event" is actually `add_event` in `src/db/database_handler.py`; threaded
through `src/core/event_lifecycle.py`. Ephemeral/lite path needed no change
(blank name by default).

## Verification

- `uv run pytest` (full suite passes)
- `uv run ruff check src/ tests/` clean
- `uv run ty check src/` clean (if unchanged surface)
- Manual: create event with organizer name → RSVP link shows it → attendee page
  shows it; RSVP result + card modal show the clarifying line.

---

# Round 3 (2026-10-15) — Card dialogs can't be skipped after a fresh mint

Approved in chat: organizer and invite cards are the *required* credential, so
once a fresh key is minted the card dialog must be the only way forward. The
footer Cancel is removed from the card dialog everywhere; fresh-key dialogs are
fully locked (no ×, backdrop clicks inert); the workspace "Organizer card"
re-open stays dismissable via × and backdrop as today — no fresh key is at
stake there.

## Goal

After creating an event, minting a key, an RSVP mint, or the lite/flyer form,
the card dialog cannot be dismissed — the only exit is producing the card
(Save to Photos / Save / Download card). "Fresh" =
the four call sites that already pass `fresh: true` to `openCardCoverModal`.

## Requirements

- [x] `openModal` gains `dismissable = true`. When false: no `.modal-close`
      (×), backdrop clicks ignored, no footer Cancel. The `.modal-actions` row
      renders only when it will contain a button; `cancelText: null` hides the
      cancel button (mirror of the existing `confirmText: null`). Defaults keep
      every other dialog's markup unchanged.
- [x] `openCardCoverModal`: pass `cancelText: null` always and
      `dismissable: !card.fresh`. Fresh call sites: create event (L452),
      key mint (L1355), RSVP result (L2120), lite/flyer (L2393); organizer
      re-open (L575) stays dismissable.
- [x] Share-capable dialogs get a single action: iOS "Save to Photos", other
      platforms "Save" (renamed from "Share card"). "Download to Files" is
      removed on every platform as redundant (button, listener and stale
      comment deleted); share success closes the dialog (existing behavior).
      Non-share-capable keeps the "Download card" footer confirm.
- [x] E2E helpers complete the mandatory card step (`expect_download` +
      confirm) instead of clicking Cancel.
- [x] E2E: lock pinned by a new test; existing flows updated; docs one-liners.

## Out of scope

- Browser-level exits (reload / close tab / navigation). No beforeunload guard:
  a reload loses the fresh key exactly as today's Cancel did.
- Bulk key generation (already auto-downloads card files; no dialog).
- Copy changes inside the card dialog.
- `test_lite.py` flows that `goto` away mid-dialog (implicit exit by design).

## Approach

1. `web/app.js` `openModal` (~L174): signature gains `dismissable = true`;
   render the head × only when dismissable; render the `.modal-actions` block
   only when ≥1 button will show; render the cancel button only when
   `dismissable && cancelText`; bind the backdrop close only when dismissable.
2. `web/app.js` `openCardCoverModal` (~L1102, ~L1144, ~L1176): pass
   `cancelText: null`, `dismissable: !card.fresh`; `primaryLabel` becomes
   `shareCapable ? (isIOS ? "Save to Photos" : "Save") : "Download card"`;
   the share-capable body renders only that single button; delete the
   "Download to Files" button, its `filesBtn` listener, and the stale
   share-flow comment (~L1083-1088 rewritten).
3. `tests/e2e/pages.py`: `create_event` (L148), `mint_key` (L201),
   `unlock_from_rsvp_result` (L374) finish the locked dialog via
   `expect_download()` + confirm click; assert the suggested-filename suffix
   (`organizer card.png` / `invite.png`). Docstrings updated.
4. `tests/e2e/test_organizer_flows.py`: `test_flyer_upload_shows_cover_option`
   closes the organizer re-open dialog via `#modal-root .modal-close`;
   `test_mint_modal_never_shows_key_text` completes via download; NEW
   `test_fresh_card_modal_is_locked` (no cancel, no ×, backdrop click inert,
   closes only after download; organizer re-open has a working ×).
5. `tests/e2e/test_card_save_share.py`: module docstring rewritten; the
   iPhone test asserts "Save to Photos" is the dialog's only action (no
   `download-files`, order `["save-share"]`); the abort test's expected
   desktop label becomes "Save" and it also asserts the locked RSVP dialog
   offers no cancel/×.
6. Docs: `docs/project_memory.md` dated entry;
   `docs/steganography_invites.md` card-first paragraph gains the
   "unskippable once minted" clause.

## Verification

```bash
uv run pytest -q                     # unit
uv run pytest tests/e2e -m e2e -q    # browser e2e
uv run ruff check src tests
node --check web/app.js
```

## Edge cases to test

- Locked fresh dialog: no cancel/×, backdrop inert, exit only via card export.
- Organizer re-open: × closes it (backdrop still closes, as today).
- Share-capable locked (all platforms): single action; success closes the
  dialog; AbortError keeps it open and silent, button re-enabled.
- iOS share-capable: button says "Save to Photos"; Android/desktop: "Save".
  No empty footer row on any share-capable dialog.
- Download failure: dialog stays open, confirm re-enabled (existing behavior).

## Progress

- [x] T1. `openModal` dismissable option + conditional close wiring.
- [x] T2. `openCardCoverModal` wiring: `cancelText: null`,
      `dismissable: !card.fresh`, single-action share body ("Save to Photos" /
      "Save"), delete Download to Files + listener + stale comment.
- [x] T3. E2E helpers rework (`create_event`, `mint_key`, `unlock_from_rsvp_result`).
- [x] T4. E2E test updates (lock test, flyer ×, abort + iPhone asserts).
- [x] T5. Docs one-liners.
- [x] T6. Full verification, real output reported.

### Status — implemented & verified (2026-10-15)

- `uv run pytest -q` → 315 passed, 41 deselected
- `uv run pytest tests/e2e -m e2e -q` → 41 passed
- `uv run ruff check src tests` → clean; `ruff format --check` → clean
- `node --check web/app.js` → OK

## Review findings (filled by reviewer agent)

- **[fixed — was a blocker]** Keyboard escape from locked dialogs (reviewer
  repro: Tab ×7 from the minted-key dialog reached `#ws-organizer-card`; Enter
  opened the re-open modal, whose `openModal` → `closeModal()` force-remove
  destroyed the fresh dialog and its only copy of the key). Fix: `web/app.js`
  `setBackgroundInert` — every top-level container except `#modal-root` goes
  `inert` while a non-dismissable dialog is open (applied in `openModal`,
  restored in `closeModal` and the dialog's local `close`). Pinned by a new
  Tab-escape assertion in `test_fresh_card_modal_is_locked` (RED → GREEN);
  full suite re-run clean after the fix.
- Non-blocking notes (deferred): "share success closes the dialog" and
  "re-open backdrop still closes" are not asserted directly (the share close
  is transitively proven: the toast is emitted inside `doShare`, `closeModal()`
  is the unconditional next statement).

---

# Privacy-Preserving Directions Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a tap-to-load MapLibre map and open-source directions links to standard and lite event pages, with encrypted geocoded coordinates and a per-event map switch.

**Architecture:** Geocode once at creation (or when the map is enabled) via Nominatim and store the result encrypted in `events.location_geo`. Serve a vendored MapLibre build from `web/vendor/`; lazy-load it only when the attendee taps "Show map"; fetch OpenFreeMap vector tiles directly from the browser. A shared `web/map_widget.js` mounts the widget on the SPA and the server-rendered lite page. The Pi never proxies tiles.

**Tech Stack:** Python 3.11, FastAPI, SQLite + Fernet, vanilla JS, MapLibre GL JS 6.11.1 (vendored ESM), OpenFreeMap vector tiles, Nominatim, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-19-privacy-preserving-directions-map-design.md`

## Global Constraints

- No CDN; vendor a pinned MapLibre build with its license and SHA-256.
- No server-side tile proxy, static image rendering, or per-view geocoding.
- `Referrer-Policy: no-referrer` on every response, plus meta tags in `web/index.html` and `_render_page`.
- Coordinates encrypted at rest; the public RSVP view never exposes them.
- Dark-only UI; terse copy; no helper paragraphs (design-system §3.4).
- Geocode only when a map style is configured, a geocoder is configured, `show_map` is true, and the address is non-empty.
- `map_available` is true only when coordinates are stored, `show_map` is true, and a map style is configured.
- Schema column order: `organizer_name` index 12, `location_geo` 13, `show_map` 14.
- Existing additive migration pattern via `_ensure_column`.

## Review Focus

- Map-off creation must not send the address to Nominatim; toggling on later must geocode once and show "Map unavailable" on failure.
- The lite page is public; the map must not add a new location leak, and no third-party request happens before tap.
- Malformed or missing `location_geo` must not break the event page or leak plaintext.
- No key or event URL may leak through Referer to OpenFreeMap or outbound links.
- Only the organizer key can toggle `show_map`; a non-organizer key gets 400 and the value is unchanged.

## File Structure

- Create `src/core/geocoding.py` — `GeoPoint`, `Geocoder` protocol, `NominatimGeocoder`, env builder.
- Modify `src/db/database_handler.py` — schema, add/get, setters.
- Modify `src/core/event_lifecycle.py` — create-time geocoding, `set_event_map`.
- Modify `src/ephemeral/service.py` — lite geocoding and public-view fields.
- Modify `src/ephemeral/routes.py` — lite form switch, map markup, no-referrer meta.
- Modify `src/api/server.py` — request models, toggle route, config wiring, referrer middleware.
- Modify `src/api/gateway.py` — `map_style_url` inside the event response.
- Create `web/map_widget.js` — shared lazy map widget.
- Create `web/vendor/maplibre/` — pinned MapLibre build, license, README with hashes.
- Modify `web/index.html` — no-referrer meta, widget script, Map checkboxes.
- Modify `web/app.js` — create/lite forms, event page rendering, workspace toggle.
- Modify `web/style.css` — map widget and toggle styles.
- Modify `tests/test_database_handler.py`, `tests/test_event_lifecycle.py`, `tests/test_api_server.py`, `tests/test_ephemeral.py`, `tests/e2e/pages.py`, `tests/e2e/conftest.py`.
- Create `tests/test_geocoding.py`, `tests/test_map_api.py`, `tests/e2e/test_map_widget.py`.
- Modify `docs/threat_model.md`, `docs/design_system.md`, `docs/project_memory.md`, `roadmap.md`, `README.md`.

---

### Task 1: Encrypted coordinates and map switch in the DB

**Files:**
- Modify: `src/db/database_handler.py`
- Test: `tests/test_database_handler.py`

**Interfaces:**
- `DatabaseHandler.add_event(..., location_geo: str | None = None, show_map: bool = True) -> None`
- `DatabaseHandler.get_event(event_id: str) -> dict | None` adds `location_lat: float | None`, `location_lon: float | None`, `show_map: bool`
- `DatabaseHandler.set_event_location_geo(event_id: str, location_geo: str | None) -> None`
- `DatabaseHandler.set_event_show_map(event_id: str, show_map: bool) -> None`

- [x] **Step 1: Write the failing tests** in `tests/test_database_handler.py` (unittest style):
  - `test_event_map_defaults_are_empty_and_on`: `add_event("event_map", "title", "description", "organizer_id")`; `get_event` returns `location_lat is None`, `location_lon is None`, `show_map is True`.
  - `test_event_location_geo_is_encrypted_and_round_trips`: `add_event(..., location_geo='{"lat": 40.75, "lon": -73.98}')`; raw `SELECT location_geo FROM events` does not contain `"40.75"` or `"-73.98"`; `get_event` returns `40.75` / `-73.98`.
  - `test_set_event_location_geo_and_show_map`: `set_event_location_geo("event_map", '{"lat": 1.5, "lon": 2.5}')`; `set_event_show_map("event_map", False)`; `get_event` returns the coordinates and `show_map is False`.
  - `test_malformed_location_geo_returns_no_coordinates`: store `db._encrypt("{not json")` in `location_geo`, commit; `get_event` returns `None` for both coordinates and does not raise.
  - `test_fresh_schema_map_column_order`: `PRAGMA table_info(events)`; assert column names at indices 12/13/14 are `organizer_name`, `location_geo`, `show_map`.
  - `test_legacy_db_migrates_map_columns`: create a temp sqlite file with the pre-map `events` table (columns through `organizer_name`), open `DatabaseHandler(path, organizer_key=TEST_ORGANIZER_KEY)`, assert the new columns exist and `add_event`/`get_event` round-trips. Follow the legacy-DB setup in `tests/test_ephemeral.py::TestSchemaMigration`.

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_database_handler.py -q`
Expected: failures for missing columns/keys.

- [x] **Step 3: Implement in `src/db/database_handler.py`**
  - Add `organizer_name TEXT`, `location_geo TEXT`, `show_map INTEGER NOT NULL DEFAULT 1` to `CREATE TABLE events` after `slug` (indices 12/13/14).
  - Add `_ensure_column("events", "location_geo", "TEXT")` and `_ensure_column("events", "show_map", "INTEGER NOT NULL DEFAULT 1")` to `_migrate_schema`; keep the existing `organizer_name` call before them.
  - Add `_EVENT_LOCATION_GEO_MIN_COLS = 13`, `_EVENT_SHOW_MAP_MIN_COLS = 14`.
  - `get_event`: decrypt `result[13]` when present, parse JSON, return `location_lat`/`location_lon` (float or None). A `DecryptionError` propagates like `location_data`; malformed JSON logs `logger.warning("Malformed location_geo for event %s", event_id)` and returns None for both. `show_map` is `bool(result[14])` when present, else `True`.
  - `add_event`: add the two parameters, encrypt `location_geo` with `_encrypt` when non-empty, insert `location_geo` and `show_map` (`1`/`0`).
  - Add `set_event_location_geo` (encrypt/update/commit) and `set_event_show_map` (update/commit).

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_database_handler.py -q`
Expected: pass.

- [x] **Step 5: Commit**

```bash
git add src/db/database_handler.py tests/test_database_handler.py
git commit -m "feat(db): store encrypted event coordinates and map switch"
```

---

### Task 2: Cached Nominatim geocoder

**Files:**
- Create: `src/core/geocoding.py`
- Test: `tests/test_geocoding.py`

**Interfaces:**
- `@dataclass(frozen=True) class GeoPoint: lat: float; lon: float`
- `class Geocoder(Protocol): def geocode(self, address: str) -> GeoPoint | None: ...`
- `NominatimGeocoder(base_url: str, user_agent: str, timeout: float = 3.0, cache_ttl: float = 86400.0, max_cache: int = 256, clock: Callable[[], float] | None = None, sleep: Callable[[float], None] | None = None, fetch: Callable[[urllib.request.Request, float], bytes] | None = None)`
- `NominatimGeocoder.geocode(address: str) -> GeoPoint | None`
- `build_geocoder_from_env() -> NominatimGeocoder | None`
- Constants: `DEFAULT_MAP_STYLE_URL = "https://tiles.openfreemap.org/styles/dark"`, `DEFAULT_GEOCODER_URL = "https://nominatim.openstreetmap.org"`, `DEFAULT_GEOCODER_USER_AGENT = "gatekeyp/0.1 (+https://cellar.otxwes.nohost.me)"`

- [x] **Step 1: Write the failing tests** in `tests/test_geocoding.py` with pytest and a fake `fetch`:
  - `test_geocode_returns_first_result`: fake returns `b'[{"lat":"40.75","lon":"-73.98"}]'`; assert `GeoPoint(40.75, -73.98)` and the request URL contains `format=jsonv2`, `limit=1`, and the encoded address.
  - `test_geocode_returns_none_on_empty_results`: fake returns `b"[]"`.
  - `test_geocode_returns_none_on_fetch_error`: fake raises `urllib.error.URLError("down")`; assert None and `caplog` contains no address.
  - `test_geocode_caches_positive_results`: fake counts calls; two identical geocodes call it once.
  - `test_geocode_normalizes_cache_key`: `"  Main St  "` and `"main st"` share one fetch.
  - `test_geocode_rate_limits_requests`: inject a fake clock and `sleep`; two different addresses; assert `sleep` was called with a positive value and the second request waits ~1s.
  - `test_build_geocoder_from_env_disabled`: monkeypatch `GATEKEYP_MAP_STYLE_URL=""` or `GATEKEYP_GEOCODER_URL=""`; assert None.
  - `test_build_geocoder_from_env_enabled`: set both; assert a `NominatimGeocoder` with the configured base URL and user agent.

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_geocoding.py -q`
Expected: `ImportError` / missing module.

- [x] **Step 3: Implement `src/core/geocoding.py`**
  - Normalize the cache key with `" ".join(address.split()).strip().lower()`.
  - Cache positive `GeoPoint`s with `time.monotonic()`; purge expired entries; cap at `max_cache`.
  - Serialize requests with a `threading.Lock` and enforce at least 1 second between requests using the injectable clock/sleep.
  - Build `base_url.rstrip("/") + "/search?" + urlencode({"q": address, "format": "jsonv2", "limit": 1})`.
  - Send `User-Agent` and `Accept: application/json`; default fetch uses `urllib.request.urlopen(request, timeout=timeout).read()`.
  - Parse the first result's `lat`/`lon` as floats. Catch `urllib.error.URLError`, `TimeoutError`, `OSError`, `ValueError`, `KeyError`, `TypeError`, `IndexError`; log `"Geocoding request failed"` without the address; return None.
  - `build_geocoder_from_env` reads the three env vars, returns None if the map style URL or geocoder URL is empty.

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_geocoding.py -q`
Expected: pass.

- [x] **Step 5: Commit**

```bash
git add src/core/geocoding.py tests/test_geocoding.py
git commit -m "feat(geo): add cached Nominatim geocoder"
```

---

### Task 3: Lifecycle geocoding and organizer toggle

**Files:**
- Modify: `src/core/event_lifecycle.py`
- Test: `tests/test_event_lifecycle.py`

**Interfaces:**
- `EventLifecycleManager(..., geocoder: Geocoder | None = None, map_style_url: str | None = None)`
- `create_event(..., show_map: bool = True) -> dict` adds `show_map: bool` and `map_available: bool`
- `set_event_map(organizer_key: str, event_id: str, show_map: bool) -> dict` returns `{"show_map": bool, "map_available": bool}`

- [x] **Step 1: Write the failing tests** in `tests/test_event_lifecycle.py` with a local `FakeGeocoder` (records calls, returns a configurable `GeoPoint | None`):
  - `test_create_event_geocodes_when_map_on`: lifecycle with fake + `map_style_url="https://example.test/style.json"`; create with `location_data="Main St"`; response `map_available is True`; `db.get_event` has the coordinates.
  - `test_create_event_skips_geocode_when_map_off`: `show_map=False`; fake not called; coords None; `map_available is False`.
  - `test_create_event_survives_geocode_failure`: fake returns None; event created; coords None; `map_available is False`.
  - `test_create_event_without_geocoder_has_no_map`: no geocoder; coords None.
  - `test_set_event_map_rejects_non_organizer_key`: create an access key; `set_event_map(access_key, ...)` raises `EventLifecycleError`.
  - `test_set_event_map_off_keeps_coordinates`: create with map on; toggle off; coords unchanged; `show_map` false; `map_available` false.
  - `test_set_event_map_on_geocodes_missing_coordinates`: create with map off (no coords); toggle on; fake called once; coords stored; `map_available` true.
  - `test_set_event_map_on_without_location_raises`: create without `location_data`; toggle on raises `EventLifecycleError`.
  - `test_set_event_map_on_geocode_failure_returns_unavailable`: create with map off; fake returns None; toggle on; `show_map` true, `map_available` false.

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_event_lifecycle.py -q`
Expected: failures for missing parameters/fields.

- [x] **Step 3: Implement in `src/core/event_lifecycle.py`**
  - Store `geocoder` and `map_style_url`.
  - In `create_event`, after validation and before `add_event`: if `show_map` and `self.geocoder` and `location_data.strip()`, geocode; on success set `location_geo = json.dumps({"lat": point.lat, "lon": point.lon})`. Pass `location_geo` and `show_map` to `add_event`. Add `"show_map": show_map` and `"map_available": bool(location_geo) and bool(self.map_style_url)` to the return dict.
  - Add `_verify_event_organizer(organizer_key, event_id) -> dict` using the same key validation/content-link checks as `get_event_details`; refactor `get_event_details` to use it.
  - `set_event_map`: verify; if enabling, require `location_data`; if enabling and `location_lat is None` and a geocoder exists, geocode and `set_event_location_geo`; call `set_event_show_map`; re-read the event; return `{"show_map": show_map, "map_available": bool(show_map and event.get("location_lat") is not None and self.map_style_url)}`.

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_event_lifecycle.py -q`
Expected: pass.

- [x] **Step 5: Commit**

```bash
git add src/core/event_lifecycle.py tests/test_event_lifecycle.py
git commit -m "feat(events): geocode map locations and toggle the map"
```

---

### Task 4: API config, toggle route, and event response

**Files:**
- Modify: `src/api/server.py`
- Modify: `src/api/gateway.py`
- Create: `tests/test_map_api.py`

**Interfaces:**
- `CreateEventRequest.show_map: bool = True`
- `SetEventMapRequest(organizer_key: str, show_map: bool)`
- `POST /api/events/{event_id}/map` → `{"show_map": bool, "map_available": bool}`
- `Gateway(..., map_style_url: str | None = None)`
- `create_app(..., ephemeral: EphemeralService | None = None)` for test injection
- `_new_app` adds `Referrer-Policy: no-referrer`

- [x] **Step 1: Write the failing tests** in `tests/test_map_api.py` with a `map_client` fixture that injects a `FakeGeocoder`, `EventLifecycleManager(..., geocoder=fake, map_style_url="https://example.test/style.json")`, `Gateway(..., map_style_url="https://example.test/style.json")`, and `create_app(..., lifecycle=..., gateway=...)`:
  - `test_create_event_defaults_show_map_true`: POST `/api/events` with a location; response `show_map is True`, `map_available is True`.
  - `test_create_event_show_map_false_skips_geocode`: fake call count 0; response `show_map is False`, `map_available is False`.
  - `test_door_response_includes_map_style_url_inside_event`: POST `/api/access` with the organizer key and event id; `data["map_style_url"] == "https://example.test/style.json"`, `data["location_lat"] == 40.75`, `data["show_map"] is True`.
  - `test_door_response_omits_map_style_url_when_disabled`: a client whose gateway has `map_style_url=None`; assert the key is absent.
  - `test_toggle_route_rejects_non_organizer_key`: generate an access key; POST `/api/events/{id}/map` with it → 400; DB `show_map` unchanged.
  - `test_toggle_route_off_then_on`: toggle off → `show_map False`; toggle on → `show_map True`; fake geocoder not called on the second call (coordinates already stored).
  - `test_toggle_route_on_geocodes_missing_coordinates`: create with `show_map=False`; toggle on → fake called once; response `map_available True`.
  - `test_toggle_route_on_without_location_returns_400`.
  - `test_referrer_policy_header`: GET `/health`; `response.headers["referrer-policy"] == "no-referrer"`.
  - `test_rsvp_public_view_excludes_map_fields`: create with a location; GET `/api/events/{id}/rsvp/view`; assert `location_lat`, `location_lon`, `show_map`, and `map_style_url` are absent from `event`.

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_map_api.py -q`
Expected: failures for missing model fields/route.

- [x] **Step 3: Implement**
  - `src/api/server.py`: add `show_map` to `CreateEventRequest`; add `SetEventMapRequest`; pass `show_map` in the create route; add the `POST /api/events/{event_id}/map` route with the existing `EventLifecycleError` → 400 pattern; add the `ephemeral` injection parameter.
  - `src/api/server.py`: in `create_app`, read `GATEKEYP_MAP_STYLE_URL` (default `DEFAULT_MAP_STYLE_URL`, empty → None), build the geocoder with `build_geocoder_from_env()`, and pass `geocoder`/`map_style_url` to the constructed lifecycle and ephemeral service, and `map_style_url` to the gateway. If a service is injected, leave it as provided.
  - `src/api/server.py`: add the `Referrer-Policy` middleware to `_new_app`.
  - `src/api/gateway.py`: add the optional `map_style_url`; in `process_request`, when the content is an event and the style URL is set, add `content["map_style_url"] = self.map_style_url` inside the event dict.

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_map_api.py tests/test_api_server.py -q`
Expected: pass.

- [x] **Step 5: Commit**

```bash
git add src/api/server.py src/api/gateway.py tests/test_map_api.py
git commit -m "feat(api): expose map config and toggle route"
```

---

### Task 5: Lite service geocoding and public-view fields

**Files:**
- Modify: `src/ephemeral/service.py`
- Test: `tests/test_ephemeral.py`

**Interfaces:**
- `EphemeralService(..., geocoder: Geocoder | None = None, map_style_url: str | None = None)`
- `create_lite_event(..., show_map: bool = True) -> dict` adds `show_map: bool`, `map_available: bool`
- `get_public_view` event adds `location_lat`, `location_lon`, `show_map`, `map_style_url`

- [x] **Step 1: Write the failing tests** in `tests/test_ephemeral.py` using a `map_ephemeral` fixture built with a `FakeGeocoder` and `map_style_url="https://example.test/style.json"`:
  - `test_lite_create_geocodes_where_when_map_on`: create with `where="Main St"`; response `map_available True`; `get_public_view` event has the coords, `show_map True`, `map_style_url` set.
  - `test_lite_create_skips_geocode_when_map_off`: fake call count 0; response `map_available False`; public view coords None.
  - `test_lite_create_survives_geocode_failure`: fake returns None; event created; `map_available False`.
  - `test_lite_public_view_includes_map_fields`: assert the four fields are inside `view["event"]`.

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ephemeral.py -q`
Expected: failures for missing parameters/fields.

- [x] **Step 3: Implement**
  - Store `geocoder` and `map_style_url` in the constructor.
  - In `create_lite_event`, after `where` validation, geocode when `show_map`, the geocoder exists, and `where` is non-empty; build the encrypted JSON after `lifecycle.create_event` with `self.db.set_event_location_geo`. Pass `show_map` to `lifecycle.create_event`.
  - Add `"show_map": show_map` and `"map_available": bool(location_geo) and bool(self.map_style_url)` to the return dict.
  - In `get_public_view`, add `map_style_url` inside the `event` dict; the coordinates and `show_map` come from `get_event`.

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ephemeral.py -q`
Expected: pass.

- [x] **Step 5: Commit**

```bash
git add src/ephemeral/service.py tests/test_ephemeral.py
git commit -m "feat(lite): geocode lite locations for the map"
```

---

### Task 6: Lite page map markup and no-referrer meta

**Files:**
- Modify: `src/ephemeral/routes.py`
- Test: `tests/test_ephemeral.py`

**Interfaces:**
- `_render_live_page(..., location_lat: float | None, location_lon: float | None, show_map: bool, map_style_url: str | None)`
- `_map_links(lat: float | None, lon: float | None, title: str, address: str | None) -> str`
- `_render_page` includes `<meta name="referrer" content="no-referrer">`

- [x] **Step 1: Write the failing tests** in `tests/test_ephemeral.py`:
  - Build the map-enabled lite client with `create_app(profile="lite", ephemeral=map_ephemeral)` (the `ephemeral` injection parameter from Task 4).
  - `test_live_page_renders_map_placeholder_and_links`: GET `/i/{id}` for a geocoded lite event; assert `data-gatekeyp-map`, `data-lat`, `data-lon`, `Show map`, the OSM/Organic Maps/OsmAnd hrefs, the OpenFreeMap/OpenMapTiles/OSM attribution, and `/map_widget.js`.
  - `test_live_page_omits_map_when_show_map_false`: no `data-gatekeyp-map`; the links still appear.
  - `test_live_page_omits_map_without_coordinates_but_shows_osm_search`: no map; an `openstreetmap.org/search?query=` link and `data-copy-address`.
  - `test_live_page_has_no_referrer_meta`: the response body contains `<meta name="referrer" content="no-referrer">`.
  - `test_lite_create_form_show_map_false`: POST the form with `show_map=0`; the created event's `show_map` is false and the fake geocoder is not called.

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ephemeral.py -q`
Expected: failures for missing markup/fields.

- [x] **Step 3: Implement**
  - Extend `_render_live_page` with the four parameters; render the map figure and link row only when `show_map` and coordinates and `map_style_url` exist; always render the links when `where` exists (OSM search + copy when coordinates are absent).
  - Add `_map_links` with the exact URLs from the spec; all external links use `target="_blank" rel="noopener noreferrer"`.
  - Add the attribution line and `<script src="/map_widget.js" defer></script>`.
  - Add the no-referrer meta to `_render_page`.
  - Parse the hidden `show_map=0` / checkbox `show_map=1` form field in `create_lite_event` (the checkbox markup is added in Task 8).
  - Pass the new event fields from `get_public_view` in `lite_og_page`.

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ephemeral.py -q`
Expected: pass.

- [x] **Step 5: Commit**

```bash
git add src/ephemeral/routes.py tests/test_ephemeral.py
git commit -m "feat(lite): render the directions map on the share page"
```

---

### Task 7: Vendored MapLibre and shared map widget

**Files:**
- Create: `web/map_widget.js`
- Create: `web/vendor/maplibre/maplibre-gl.mjs`, `maplibre-gl-shared.mjs`, `maplibre-gl-worker.mjs`, `maplibre-gl.css`, `LICENSE.txt`, `README.md`
- Modify: `web/index.html`
- Modify: `web/style.css`

**Interfaces:**
- `window.GatekeypMap = { mount(el: HTMLElement): void, autoMount(): void }`
- Lazy-loads `/vendor/maplibre/maplibre-gl.mjs`; calls `setWorkerUrl("/vendor/maplibre/maplibre-gl-worker.mjs")`
- Map options: center `[lon, lat]`, zoom 16, `cooperativeGestures: true`, `dragRotate: false`, `touchPitch: false`, `pitchWithRotate: false`, `attributionControl: false`, one `NavigationControl({ showCompass: false })`
- On failure: button text "Map unavailable", disabled; links stay

- [x] **Step 1: Vendor MapLibre**
  - Download the `maplibre-gl@6.11.1` npm tarball, extract the five dist files plus `LICENSE.txt` into `web/vendor/maplibre/`.
  - Write `web/vendor/maplibre/README.md` with the version, source URL, and SHA-256 of each file.
  - Do not load from a CDN.

- [x] **Step 2: Write `web/map_widget.js`**
  - IIFE; `loadLib()` caches a promise, appends the CSS `<link>`, dynamically imports the ESM build, and calls `setWorkerUrl`.
  - `mount(el)` is idempotent; reads `data-lat`, `data-lon`, `data-style`, `data-title`, `data-address`; attaches the "Show map" click; creates the map on the canvas child; adds the marker and zoom control; hides the button.
  - Listen for the map's `error` event before the first `load`; on a style/source failure, call `fail(el)` (button text "Map unavailable", disabled). Ignore tile errors after the map has loaded.
  - `autoMount()` mounts every `[data-gatekeyp-map]`; run it on DOMContentLoaded.
  - Delegate `[data-copy-address]` clicks to copy the address from the nearest `[data-address]` using `navigator.clipboard` with a hidden-textarea fallback.
  - Never log the address or coordinates; never add query params to the style/tile URL.

- [x] **Step 3: Wire `web/index.html` and CSS**
  - Add `<meta name="referrer" content="no-referrer">` to the head.
  - Add `<script src="map_widget.js"></script>` before `app.js`.
  - Add `.event-map`, `.event-map-canvas`, `.event-map-load`, `.event-map-links`, `.map-attribution`, and `.ws-map-toggle` styles to `web/style.css`; dark palette, 200px map card, dotted placeholder, terse link row.

- [x] **Step 4: Verify syntax**

Run: `node --check web/map_widget.js && node --check web/app.js`
Expected: no output, exit 0.

- [x] **Step 5: Commit**

```bash
git add web/map_widget.js web/vendor/maplibre web/index.html web/style.css
git commit -m "feat(web): vendor MapLibre and add the lazy map widget"
```

---

### Task 8: Standard event page, create form, and workspace toggle

**Files:**
- Modify: `web/app.js`
- Modify: `web/index.html`
- Modify: `tests/e2e/pages.py`

**Interfaces:**
- `create_event` request body includes `show_map`; `org.meta.showMap` stores the create response value.
- `renderEventPage` renders the map figure/links and calls `window.GatekeypMap.mount`.
- Workspace header renders `#ws-map-toggle`; `loadWorkspaceMapState()` reads `fetchEventDetails().event.show_map`; the change handler calls `POST /api/events/{id}/map`.
- `OrganizerPage.create_event(..., show_map: bool = True)` unchecks `#show-map` when false.

- [x] **Step 1: Update the create form handler**
  - Read `show_map` from the checkbox; include it in the `/api/events` body; set `org.meta.showMap = created.show_map ?? show_map`.
  - If `show_map` and the location is non-empty and `created.map_available === false`, show the existing toast pattern: `toast("Map unavailable. The address could not be geocoded.", "info", "Event created")`.
  - Add the checkbox to `#create-event-form` (checked by default) and to the lite form (hidden `show_map=0` before the checkbox `show_map=1`, checked).

- [x] **Step 2: Render the standard event page map**
  - In `renderEventPage`, after the address line, render the map figure when `event.show_map && event.location_lat != null && event.location_lon != null && event.map_style_url`; render the link row when `event.location_data` (app links with coordinates, OSM search + copy without).
  - Add a JS `mapLinks(event)` helper using the exact URLs from the spec.
  - After setting `root.innerHTML`, call `window.GatekeypMap.mount` on the figure.
  - Add the attribution line.

- [x] **Step 3: Add the workspace toggle**
  - In `renderWorkspace`, after the location line, render a `#ws-map-toggle` checkbox only when `org.meta.locationData` exists.
  - Add `loadWorkspaceMapState()`: fetch event details, set the checkbox from `details.event.show_map`, and enable it. Call it from `renderWorkspace`.
  - On change: disable the checkbox, POST `/api/events/{eventId}/map` with `{organizer_key, show_map}`, update `org.meta.showMap`, show "Map unavailable." if the toggle is on and `map_available` is false; on error, revert and toast.

- [x] **Step 4: Update the lite flyer form**
  - The lite form includes the hidden `show_map=0` + checkbox `show_map=1` (Task 7); its `FormData` carries the value automatically.
  - After the `/api/lite/events` response, read `show_map` and `map_available`; if `show_map` is true, the Where field is non-empty, and `map_available` is false, append a terse `Map unavailable.` line to the lite result panel.

- [x] **Step 5: Update the e2e page object**
  - `OrganizerPage.create_event(..., show_map: bool = True)`; if `show_map` is false, uncheck `#show-map` before clicking create.

- [x] **Step 6: Verify syntax and commit**

Run: `node --check web/app.js`
Expected: exit 0.

```bash
git add web/app.js web/index.html tests/e2e/pages.py
git commit -m "feat(web): show directions and the map toggle on event pages"
```

---

### Task 9: E2E coverage with a local Nominatim mock

**Files:**
- Modify: `tests/e2e/conftest.py`
- Create: `tests/e2e/test_map_widget.py`

**Interfaces:**
- `mock_nominatim` fixture: a local `ThreadingHTTPServer` returning `[{"lat":"40.75","lon":"-73.98"}]` for `/search`, and `[]` when the query contains `"nowhere"`.
- `server` fixture sets `GATEKEYP_GEOCODER_URL` to the mock's URL.
- Playwright route `https://tiles.openfreemap.org/styles/dark` fulfills a minimal style: `{"version":8,"sources":{},"layers":[{"id":"bg","type":"background","paint":{"background-color":"#111"}}]}`.

- [x] **Step 1: Write the failing tests** in `tests/e2e/test_map_widget.py`:
  - `test_standard_event_map_is_tap_to_load`: create an event with a location; unlock the attendee page; assert the address, `[data-gatekeyp-map]`, "Show map", the links, and the attribution. Collect requests to `tiles.openfreemap.org`; assert none before the click. Click "Show map"; intercept the style; assert `.maplibregl-canvas` is visible and the button is gone.
  - `test_map_links_and_copy_address`: assert the OSM/Organic Maps/OsmAnd hrefs contain the coordinates; click `[data-copy-address]` and read the clipboard.
  - `test_map_off_hides_card_but_keeps_links`: create with `show_map=False`; assert no map card/button; assert the OSM search link and copy address.
  - `test_geocode_failure_falls_back_to_osm_search`: create with `location="nowhere"`; assert no map; OSM search link present.
  - `test_lite_page_renders_map_widget`: create a lite event with `where` and map on; GET `/i/{id}`; assert the placeholder/links and the no-referrer meta; click and assert the canvas with the intercepted style.
  - `test_lite_map_off_hides_card_but_keeps_links`: create a lite event with the Map checkbox unchecked; assert no map card/button, but the OSM search link and copy address remain.
  - `test_map_load_failure_shows_unavailable`: abort the style request, click "Show map", and assert the button becomes "Map unavailable" while the links remain.
  - `test_workspace_toggle_updates_attendee_page`: create with map on; open the workspace; uncheck `#ws-map-toggle`; reload the attendee page and assert no map card but links remain; check it again; reload and assert the placeholder returns.
  - `test_no_referrer_header`: `page.request.get(f"{base}/health")`; assert `Referrer-Policy: no-referrer`; assert `meta[name="referrer"][content="no-referrer"]` on the standard page.

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/e2e/test_map_widget.py -m e2e -q`
Expected: failures for missing fixtures/selectors.

- [x] **Step 3: Implement the mock Nominatim and the page helpers**
  - Add the `mock_nominatim` fixture in `tests/e2e/conftest.py`; make `server` depend on it and set `GATEKEYP_GEOCODER_URL`.
  - Add the style interception helper in the test module.
  - Use the existing `OrganizerPage`/attendee helpers to unlock the standard event page.

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/e2e/test_map_widget.py -m e2e -q`
Expected: pass.

- [x] **Step 5: Commit**

```bash
git add tests/e2e/conftest.py tests/e2e/test_map_widget.py
git commit -m "test(e2e): cover the tap-to-load directions map"
```

---

### Task 10: Documentation and full verification

**Files:**
- Modify: `docs/threat_model.md`
- Modify: `docs/design_system.md`
- Modify: `docs/project_memory.md`
- Modify: `roadmap.md`
- Modify: `README.md`

- [x] **Step 1: Update the docs**
  - Threat model: add the geocoding and map data flow, the OpenFreeMap/Cloudflare metadata exposure, the tap-to-load/no-referrer mitigations, the per-event/workspace and global off switches, and the self-hosting note.
  - Design system: one note on the CSS-only placeholder, terse links, visible OpenFreeMap/OpenMapTiles/OSM attribution, and no helper prose.
  - Project memory: dated entry with what/why/verification.
  - Roadmap: Phase 4 note; check off "Select open-source map tiles" (MapLibre + OpenFreeMap); leave routing/geofencing and key-level routes unchecked.
  - README: document `GATEKEYP_MAP_STYLE_URL`, `GATEKEYP_GEOCODER_URL`, `GATEKEYP_GEOCODER_USER_AGENT`, and the empty-string disable behavior.

- [x] **Step 2: Run the full verification**

```bash
uv run pytest -q
uv run pytest tests/e2e -m e2e -q
uv run ruff check src tests
node --check web/app.js
node --check web/map_widget.js
```

Expected: all green. Capture the real output.

- [x] **Step 3: Commit**

```bash
git add docs/threat_model.md docs/design_system.md docs/project_memory.md roadmap.md README.md docs/superpowers/specs/2026-10-19-privacy-preserving-directions-map-design.md plans/PLAN.md
git commit -m "docs(map): record the directions map and its privacy boundary"
```

## Verification

- `uv run pytest -q` — full unit suite passes.
- `uv run pytest tests/e2e -m e2e -q` — browser suite passes.
- `uv run ruff check src tests` — clean.
- `node --check web/app.js` and `node --check web/map_widget.js` — valid.
- Manual smoke: create a standard event with a location and the map on; the event page shows the placeholder; tapping loads the map; the links open OSM/Organic Maps/OsmAnd; the workspace toggle removes and restores the card; create a lite event and verify the same on `/i/{id}`.

---

# Round 4 (2026-10-23) — stale-cache deploy safety + honest map feedback

Field report (2026-10-22, after the `08b0286` deploy): tapping "Show map" on
the live site did nothing. Root cause established in the main session: no
cache policy on static assets let a browser hold a pre-deploy cached
`index.html` (no widget script tag) alongside the new `app.js`, whose mount
guard silently skipped — inert button. Reproduced exactly by blocking
`map_widget.js` in a live-browser run; with fresh assets the map works
end-to-end on live. Side question settled: the standard create form never
had a date/time field (lite flyer form's When is untouched).

- [x] T1. RED: `TestStaticCachePolicy` in `tests/test_api_server.py` —
      index + `app.js` must revalidate (`no-cache`); `/health` and `/api/*`
      untouched (guard test passed pre-implementation by design).
- [x] T2. GREEN: `_new_app` gains `add_static_cache_policy` middleware —
      `Cache-Control: no-cache` via `setdefault` on non-`/api`, non-`/health`
      paths, so routes that set their own policy keep it (RSVP flyer
      `max-age=86400`).
- [x] T3. RED→GREEN e2e: `test_missing_widget_marks_map_unavailable`
      (blocks `map_widget.js`, asserts disabled "Map unavailable" + links
      row) pins the honest feedback; `web/app.js` gains `mountMap()` used at
      both mount call sites instead of the silent guard.
- [x] T4. Full verification (real output): unit 363 passed / 51 deselected;
      e2e 51 passed; ruff clean; `node --check` app.js + map_widget.js OK.
      Deploy evidence goes to the audit trail after the redeploy.

---

# Round 5 (2026-10-23) — card save UX on desktop + one map link

User-approved follow-ups after live testing.

- [x] T1. Card modal: only iOS uses the native share sheet ("Save to Photos");
      every other platform — including desktop Chrome, whose Web Share API
      accepts files — gets the plain "Download card" confirm that downloads
      the PNG directly. RED: new e2e `test_desktop_share_capable_downloads_directly`
      failed with the share button present; the abort test now runs with an
      iPhone UA. GREEN: `useShare = shareCapable && isIOS` at every decision
      point.
- [x] T2. Map link row reduced to one OpenStreetMap link; "Copy address",
      Organic Maps, and OsmAnd removed (the address is already shown above
      the card). Attribution line kept (OSM/OpenMapTiles license). Touched
      `web/app.js` mapLinks, `src/ephemeral/routes.py` `_map_links` (dropped
      the unused title param and the `.linklike` CSS), the widget's copy
      delegation, and `web/style.css`.
- [x] T3. Tests: map e2e single-link/no-copy assertions, lite unit assertions,
      card tests updated (desktop download + iOS abort). Full verification:
      unit 363 passed / 53 deselected; e2e 54 passed; ruff clean; node checks.

---

# Round 6 (2026-10-23) — "Open map" button + lite container guard

- [x] T1. The single map link is now an "Open map" button: SPA uses
      `btn btn-ghost btn-sm` on the anchor (links that navigate stay
      anchors); the lite page gets an inline `.event-map-links a`
      button-style rule. RED: e2e expected "Open map" text/class and the
      lite unit page expected the new label — both failed first.
- [x] T2. Found while here: the lite page's inline CSS still had the old
      `position:absolute;inset:0` container rule — the same collapse bug
      fixed in style.css for the SPA. Added `width/height:100%` and extended
      the lite e2e test with the container-geometry assertions.
- [x] T3. Full verification: unit 363 passed / 54 deselected; e2e 54 passed;
      ruff clean; node checks OK.

---

# Round 7 (2026-10-23) — portrait flyers fill the content column

Owner report: the flyer on the attendee event page looked tiny relative to
the page. Reproduced live with a real 600x900 PNG: content column 342px,
flyer rendered 174x260px — the shared `.event-flyer { max-height: 260px }`
cap squashed portrait art to half the page width. The 1x1 PNG fixture in the
old tests could never expose this.

- [x] T1. RED: e2e geometry test with a generated 600x900 portrait PNG —
      asserted the flyer renders at min(column, 420px) with its aspect ratio
      preserved (failed at 174 vs 420).
- [x] T2. GREEN: scoped `#join-views .event-flyer, #rsvp-views .event-flyer
      { width:100%; max-width:420px; max-height:none; height:auto }`; the
      workspace header keeps the 260px thumbnail cap.
- [x] T3. Full verification: unit 363 passed / 55 deselected; e2e 55 passed;
      ruff clean; node checks OK.
