# Transit Directions + Event Start Time — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional start date/time to standard events, and a Pi-hosted transit-directions flow that turns a typed start address into a static walk + transit itinerary (no geolocation, nothing stored server-side).

**Architecture:** Part 1 adds `events.starts_at` (additive migration) and surfaces it in the SPA. Part 2 adds `src/core/transit.py` (region selection + OpenTripPlanner GraphQL client + itinerary mapping), a `POST /api/directions` endpoint that geocodes the start via Nominatim (no cache, region-biased) and routes through a loopback OTP service, and a shared `web/directions.js` widget mounted on the SPA event page and the lite page. The feature is off unless `GATEKEYP_OTP_URL` is configured.

**Tech Stack:** Python 3.11/FastAPI, SQLite + Fernet, vanilla JS, OpenTripPlanner 2.x (GTFS GraphQL), MapLibre (existing), pytest + Playwright.

**Spec:** `docs/superpowers/specs/2026-10-24-transit-directions-design.md`

## Global Constraints

- The map toggle is the organizer's location-data opt-out: no geocoding when `show_map` is false, and no directions form while it is false.
- Directions need venue coordinates; no backfill for existing events.
- The Pi computes routes; the start address is geocoded via Nominatim (trusted third party) and sent to the local OTP instance only.
- No origin persistence or logging: no DB rows, no audit rows, no request-body logs, no itinerary cache server-side; the browser may keep the last result in `localStorage`.
- Directions are off when `GATEKEYP_OTP_URL` is empty; the map card and Open map button keep working regardless.
- `Referrer-Policy: no-referrer` stays; no geolocation API is used.
- Venue-local times in responses and UI; `starts_at` is stored verbatim from `datetime-local`.
- Terse copy, dark-only UI, no helper paragraphs (design-system §3.4).
- Additive migrations only (`_ensure_column`); column order: `starts_at` is index 15.
- Existing suite must stay green: unit + e2e + ruff + `node --check`.

## Review Focus

- **Start address never logged:** the directions endpoint must not put the start text or coordinates in audit rows, exceptions, or logs; a test asserts it.
- **Map-off events have no directions:** no geocoding at creation, no form on the page, no endpoint access.
- **No route / OTP down:** the map card and Open map button still work, with one terse failure line.
- **Ambiguous start addresses:** a short address resolves inside the event's region, while a genuine long-distance origin still resolves (soft bias).
- **Out-of-town times:** a viewer in another timezone sees the venue's departure time, not their browser's.

---

## Part 1 — Event start date/time

### Task 1: `starts_at` in the database, lifecycle, and API

**Files:**
- Modify: `src/db/database_handler.py` (constants ~line 20; `add_event` ~line 568; `get_event` ~line 530; `_migrate_schema` ~line 231)
- Modify: `src/core/event_lifecycle.py` (`create_event` ~line 86)
- Modify: `src/api/server.py` (`CreateEventRequest` ~line 37; create route ~line 329)
- Test: `tests/test_database_handler.py`, `tests/test_event_lifecycle.py`, `tests/test_api_server.py`

**Interfaces:**
- Consumes: existing `_ensure_column(table, name, decl)`, `_EVENT_SHOW_MAP_MIN_COLS` pattern.
- Produces: `DatabaseHandler.add_event(..., *, starts_at: str | None = None)`, `get_event(...)["starts_at"]: str | None`; `EventLifecycleManager.create_event(..., starts_at: str | None = None)` returning `"starts_at"` in its dict; `CreateEventRequest.starts_at: str | None`.

- [ ] **Step 1: Write failing DB tests** in `tests/test_database_handler.py`:
  - `test_event_starts_at_round_trips`: `add_event(..., starts_at="2030-01-01T19:00")`; `get_event` returns it.
  - `test_event_starts_at_defaults_to_none`: existing `add_event` call → `starts_at is None`.
  - `test_fresh_schema_starts_at_column`: `PRAGMA table_info(events)` index 15 is `starts_at`.
  - `test_legacy_db_migrates_starts_at`: pre-column events table → open handler → column exists and round-trips.
- [ ] **Step 2: Run to verify RED:** `uv run pytest tests/test_database_handler.py -q` → fails (missing column/key).
- [ ] **Step 3: Implement** in `src/db/database_handler.py`:
  - Add `starts_at TEXT` to `CREATE TABLE events` after `show_map`; `_ensure_column("events", "starts_at", "TEXT")` after the `show_map` call; `_EVENT_STARTS_AT_MIN_COLS = 15`.
  - `add_event(..., starts_at: str | None = None)` (keyword-only) inserts it.
  - `get_event` returns `"starts_at": result[15] if len(result) > _EVENT_STARTS_AT_MIN_COLS else None`.
- [ ] **Step 4: Run to verify GREEN:** `uv run pytest tests/test_database_handler.py -q`.
- [ ] **Step 5: Write failing lifecycle/API tests:**
  - lifecycle: `test_create_event_stores_starts_at`; `test_create_event_rejects_unparseable_starts_at` (e.g. `"not-a-date"` → `EventLifecycleError`).
  - API: `test_create_event_passes_starts_at` (response includes it); `test_create_event_invalid_starts_at_returns_400`.
- [ ] **Step 6: Run RED** for those tests.
- [ ] **Step 7: Implement:**
  - `create_event(..., starts_at: str | None = None)`: if provided, `datetime.fromisoformat(starts_at)` must succeed, else `EventLifecycleError("Invalid event start time")`; pass to `add_event`; include `"starts_at": starts_at` in the return dict.
  - `CreateEventRequest.starts_at: str | None = Field(default=None, max_length=64)`; pass `starts_at=request.starts_at` in the route.
- [ ] **Step 8: Run GREEN** for the touched files; then commit:
  `git add src/db/database_handler.py src/core/event_lifecycle.py src/api/server.py tests/test_database_handler.py tests/test_event_lifecycle.py tests/test_api_server.py && git commit -m "feat(events): store an optional start date and time"`

### Task 2: SPA form + display of the start time

**Files:**
- Modify: `web/index.html` (`#create-event-form` ~line 48)
- Modify: `web/app.js` (create submit handler ~line 430; `renderEventPage` ~line 2270; `renderRsvp` ~line 2080; workspace header ~line 560)
- Modify: `tests/e2e/pages.py` (`OrganizerPage.create_event`)
- Test: `tests/e2e/test_attendee.py`, `tests/e2e/test_rsvp_flow.py`

**Interfaces:**
- Consumes: `CreateEventRequest.starts_at` (Task 1).
- Produces: form field `#event-starts-at`; `formatStartsAt(iso: string): string` in `web/app.js`; e2e `OrganizerPage.create_event(..., starts_at: str = "2030-01-01T19:00")`.

- [ ] **Step 1: Write failing e2e tests:**
  - `test_event_page_shows_start_time` (`tests/e2e/test_attendee.py`): create with `starts_at="2030-01-01T19:00"`, unlock, assert the attendee page shows a formatted "When" line containing `2030` and `7:00`.
  - `test_rsvp_page_shows_start_time` (`tests/e2e/test_rsvp_flow.py`): open the funnel, assert the same.
- [ ] **Step 2: Run RED:** `uv run pytest tests/e2e/test_attendee.py::test_event_page_shows_start_time -m e2e -q` → fails (no field/display).
- [ ] **Step 3: Implement:**
  - `web/index.html`: `<div class="field"><label for="event-starts-at">When</label><input type="datetime-local" id="event-starts-at" name="starts_at" required autocomplete="off"></div>` after the location field.
  - `web/app.js`: send `starts_at` in the create POST; add `formatStartsAt` (Intl short weekday/month/day + hour/minute, venue-local naive); render `<p class="ep-when">` under the lede on the attendee page, in `renderRsvp`, and in the workspace header when `starts_at` is set.
  - `tests/e2e/pages.py`: `create_event(..., starts_at: str = "2030-01-01T19:00")`, fill `#event-starts-at` when non-empty.
- [ ] **Step 4: Run GREEN** for both tests; run the full unit + e2e suites; `node --check web/app.js`.
- [ ] **Step 5: Commit:**
  `git add web/index.html web/app.js tests/e2e/pages.py tests/e2e/test_attendee.py tests/e2e/test_rsvp_flow.py && git commit -m "feat(web): show the event start time on the create form and event pages"`

---

## Part 2 — Transit directions

### Task 3: Region config, OTP client, itinerary mapping

**Files:**
- Create: `src/core/transit.py`
- Test: `tests/test_transit.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class TransitRegion: id: str; min_lat: float; max_lat: float; min_lon: float; max_lon: float; router_id: str; timezone: str; attribution: str`
  - `DEFAULT_REGIONS: dict[str, TransitRegion]` with keys `nyc`, `la`, `mtl` (bboxes: NYC 40.4–41.1 / -74.3–-73.6, LA 33.6–34.4 / -118.7–-117.6, MTL 45.3–45.8 / -74.1–-73.4; timezones `America/New_York`, `America/Los_Angeles`, `America/Toronto`; attributions "Transit data © MTA", "Transit data © LA Metro", "Transit data © STM/exo").
  - `load_regions_from_env() -> dict[str, TransitRegion]` — `GATEKEYP_TRANSIT_REGIONS` JSON override; absent/empty → `DEFAULT_REGIONS`.
  - `select_region(lat: float, lon: float, regions: dict[str, TransitRegion]) -> TransitRegion | None`.
  - `class OtpClient: __init__(base_url: str, *, timeout: float = 5.0, fetch: Callable[[urllib.request.Request, float], bytes] | None = None); plan(self, region: TransitRegion, origin: GeoPoint, destination: GeoPoint, *, depart_at: datetime | None = None) -> dict | None` — returns the raw GraphQL `data.plan` dict, or None on any error/timeout/empty.
  - `itinerary_from_otp(plan: dict, region: TransitRegion) -> dict | None` — maps to the API response shape in the spec §7.4 (origin/destination/depart_at/arrive_at/duration_minutes/legs/attribution); returns None when no itineraries.
- Consumes: `GeoPoint` from `src.core.geocoding`.

- [ ] **Step 1: Write failing tests** in `tests/test_transit.py`:
  - `test_select_region_inside_and_outside` (NYC point → nyc; Null Island → None).
  - `test_load_regions_from_env_override_and_default` (monkeypatch env JSON; absent → DEFAULT_REGIONS).
  - `test_otp_plan_posts_graphql_query`: fake `fetch` captures the `urllib.request.Request`; assert URL ends `/otp/gtfs/v1`, body contains `plan(`, the `from`/`to` coordinates, and `numItineraries`; returns parsed `data.plan`.
  - `test_otp_plan_returns_none_on_fetch_error` and `test_otp_plan_returns_none_on_timeout` (fake raises `urllib.error.URLError` / `TimeoutError`).
  - `test_itinerary_from_otp_maps_legs_and_times`: synthetic fixture with one WALK leg and one TRANSIT leg (route shortName, headsign, from/to names, start/end times) → assert leg modes, line, stops text, duration, attribution.
  - `test_itinerary_from_otp_returns_none_without_itineraries`.
- [ ] **Step 2: Run RED:** `uv run pytest tests/test_transit.py -q` → ImportError.
- [ ] **Step 3: Implement `src/core/transit.py`.** GraphQL query (OTP 2.x GTFS API) — POST JSON `{"query": QUERY, "variables": {...}}` with `from: {lat, lon}`, `to: {lat, lon}`, `date: <ISO local>`, `transportModes: [{mode: "WALK"}, {mode: "TRANSIT"}]`, `numItineraries: 3`. Query fields: `plan { itineraries { startTime endTime duration legs { mode duration distance from { name lat lon } to { name lat lon } route { shortName longName color agency { name } } headsign startTime endTime } } }`. Catch `urllib.error.URLError`, `TimeoutError`, `OSError`, `ValueError`, `KeyError`, `TypeError`, `IndexError`; log `"OTP request failed"` without coordinates.
- [ ] **Step 4: Run GREEN:** `uv run pytest tests/test_transit.py -q`.
- [ ] **Step 5: Commit:** `git add src/core/transit.py tests/test_transit.py && git commit -m "feat(transit): add region config and the OTP client"`

### Task 4: Geocoder viewbox + no-cache mode

**Files:**
- Modify: `src/core/geocoding.py` (`NominatimGeocoder.geocode` ~line 113)
- Test: `tests/test_geocoding.py`

**Interfaces:**
- Produces: `NominatimGeocoder.geocode(address: str, *, viewbox: tuple[float, float, float, float] | None = None, use_cache: bool = True) -> GeoPoint | None` where viewbox is `(min_lat, max_lat, min_lon, max_lon)`; request gains `viewbox=<min_lon>,<min_lat>,<max_lon>,<max_lat>` and `bounded=0`; `use_cache=False` skips cache reads and writes.

- [ ] **Step 1: Write failing tests:**
  - `test_geocode_viewbox_bias_adds_params`: fake fetch asserts the URL contains `viewbox=` and `bounded=0`.
  - `test_geocode_no_cache_skips_cache`: two calls with `use_cache=False` → fetch twice.
  - Existing cache tests stay green.
- [ ] **Step 2: Run RED.**
- [ ] **Step 3: Implement** (cache key includes the viewbox when present; no-cache bypasses `_cached`/`_store`).
- [ ] **Step 4: Run GREEN** (`tests/test_geocoding.py`).
- [ ] **Step 5: Commit:** `git add src/core/geocoding.py tests/test_geocoding.py && git commit -m "feat(geo): support viewbox bias and no-cache lookups"`

### Task 5: `POST /api/directions` + config + payload flag

**Files:**
- Modify: `src/api/server.py` (`create_app` ~line 255; new request model near the others; route after `/api/events/{id}/map`)
- Modify: `src/api/gateway.py` (event payload flag)
- Modify: `src/ephemeral/service.py` (`get_public_view` event flag)
- Test: `tests/test_directions_api.py` (new)

**Interfaces:**
- Consumes: `OtpClient`, `select_region`, `load_regions_from_env`, `itinerary_from_otp` (Task 3); `geocode(..., viewbox=..., use_cache=False)` (Task 4); `db.get_tombstone`, `key_manager.validate_key`, `db.get_content_ids_for_key`.
- Produces: `DirectionsRequest(event_id: str, start: str, key: str | None = None)`; `POST /api/directions`; `create_app(..., otp: OtpClient | None = None, transit_regions: dict[str, TransitRegion] | None = None)`; event payloads gain `directions_enabled: bool`.

- [ ] **Step 1: Write failing tests** in `tests/test_directions_api.py` with a `directions_client` fixture injecting a `FakeOtp` (records calls, returns a fixture plan), `FakeGeocoder` (returns `GeoPoint(40.75, -73.98)`), `transit_regions=DEFAULT_REGIONS`, and `otp=FakeOtp()`:
  - `test_directions_requires_key_for_standard_event` (no key → 403).
  - `test_directions_lite_event_needs_no_key`.
  - `test_directions_without_venue_coordinates_422` (event created with `show_map=False`).
  - `test_directions_unconfigured_region_422` (venue outside all bboxes).
  - `test_directions_unknown_or_ended_event_404` (tombstone via `db.wipe_event`).
  - `test_directions_geocode_failure_422` (fake returns None) — and the response body does not contain the start text.
  - `test_directions_otp_failure_503`.
  - `test_directions_returns_mapped_itinerary` (legs, attribution, venue-local offset).
  - `test_directions_rate_limited_429`.
  - `test_start_address_never_logged` (caplog: the start text appears in no record).
  - `test_door_payload_includes_directions_enabled` and `test_directions_disabled_without_otp` (no `GATEKEYP_OTP_URL` → flag false, endpoint 503).
- [ ] **Step 2: Run RED.**
- [ ] **Step 3: Implement:**
  - `create_app`: read `GATEKEYP_OTP_URL` (empty → None) and `load_regions_from_env()`; construct `OtpClient` when configured; pass `otp`/`regions` to the route.
  - Payload flag (concrete): `Gateway(..., transit_regions: dict[str, TransitRegion] | None = None, directions_enabled: bool = False)` — in `process_request`, for an event payload set `content["directions_enabled"] = bool(self.directions_enabled and content.get("show_map") and content.get("location_lat") is not None and select_region(content["location_lat"], content["location_lon"], self.transit_regions or {}) is not None)`. `EphemeralService.__init__(..., transit_regions=None, directions_enabled=False)` computes the same flag in `get_public_view`.
  - Route logic per spec §7.4; standard-event key check via `validate_key` + content link; lite events (`mode == "ephemeral"`) public; `db.get_tombstone` → 404; per-IP `RateLimiter(max_attempts=10, window_seconds=60)`; geocode with `viewbox=(min_lat, max_lat, min_lon, max_lon)` and `use_cache=False`; never log the start.
- [ ] **Step 4: Run GREEN** + `tests/test_api_server.py tests/test_ephemeral.py tests/test_map_api.py`.
- [ ] **Step 5: Commit:** `git add src/api/server.py src/api/gateway.py src/ephemeral/service.py tests/test_directions_api.py && git commit -m "feat(api): serve static transit directions"`

### Task 6: Directions widget + lite page + e2e

**Files:**
- Create: `web/directions.js`, `tests/e2e/test_directions.py`
- Modify: `web/app.js` (mount in `locationHtml`/after render), `web/index.html` (script tag), `src/ephemeral/routes.py` (lite markup + script + `directions_enabled`), `web/style.css`, `tests/e2e/conftest.py` (mock OTP)

**Interfaces:**
- Consumes: `POST /api/directions`, `directions_enabled` payload flag.
- Produces: `window.GatekeypDirections = { mount(el), autoMount() }`; markup `<div data-gatekeyp-directions data-event-id="…" data-key="…">`; localStorage key `gatekeyp.directions.<event_id>`.

- [ ] **Step 1: Write the mock OTP fixture** in `tests/e2e/conftest.py`: a `ThreadingHTTPServer` on a free port returning `{"data": {"plan": {"itineraries": [...]}}}` with one WALK + one TRANSIT leg; the `server` fixture sets `GATEKEYP_OTP_URL` to it.
- [ ] **Step 2: Write failing e2e tests** in `tests/e2e/test_directions.py`:
  - `test_standard_event_directions_render`: create with location `"Main St"` (fake geocoder → 40.75,-73.98, inside NYC), unlock, fill "From", submit, assert total time, line name, and leg list.
  - `test_directions_failure_keeps_open_map`: mock OTP returns 500 → terse failure line + Open map still visible.
  - `test_directions_restore_from_local_storage`: reload → last itinerary restored.
  - `test_map_off_hides_directions`.
  - `test_lite_page_directions_render`.
- [ ] **Step 3: Run RED.**
- [ ] **Step 4: Implement `web/directions.js`** (form, fetch, render, localStorage, terse errors), mount it in the SPA after render, and render the lite markup in `_render_live_page` when `directions_enabled`. Style with the existing palette; no geolocation.
- [ ] **Step 5: Run GREEN** for the new file + full e2e; `node --check web/directions.js web/app.js`.
- [ ] **Step 6: Commit:** `git add web/directions.js web/app.js web/index.html web/style.css src/ephemeral/routes.py tests/e2e/conftest.py tests/e2e/test_directions.py && git commit -m "feat(web): add the transit directions widget"`

### Task 7: Ops, data pipeline, docs

**Files:**
- Create: `scripts/transit/build_graphs.sh` (public)
- Modify: `docs/threat_model.md`, `docs/design_system.md`, `README.md`, `roadmap.md`, `docs/project_memory.md`, `plans/PLAN.md`
- Private (not in this repo): `~/projects/lichen-site/docs/deploy-gatekeyp-runbook.md` — OTP install/systemd unit, graph rsync, refresh schedule.

**Interfaces:** none (ops/docs).

- [ ] **Step 1: Write `scripts/transit/build_graphs.sh`** — per region: download GTFS zips and the OSM metro extract into `build/`, run `otp --build --save`, output `graphs/<id>/`; print sizes; no credentials; document the refresh cadence in comments.
- [ ] **Step 2: Update docs** — threat model (origin transiently visible to host, Nominatim hop, no logging/storage, rate limit); design system (terse itinerary list); README (`GATEKEYP_OTP_URL`, `GATEKEYP_TRANSIT_REGIONS`, empty disables); roadmap (routing checkbox note); project memory (dated entry); `plans/PLAN.md` (round entry pointing here).
- [ ] **Step 3: Private runbook** — add the OTP systemd unit (loopback 8080, `-Xmx3g`), graph rsync, and a post-refresh smoke check (`/otp/gtfs/v1` plan per region).
- [ ] **Step 4: Full verification:** `uv run pytest -q`; `uv run pytest tests/e2e -m e2e -q`; `uv run ruff check src tests`; `node --check web/app.js web/directions.js`.
- [ ] **Step 5: Commit:** `git add scripts/transit/build_graphs.sh docs README.md roadmap.md plans/PLAN.md && git commit -m "docs(transit): document the data pipeline and privacy boundary"`

---

## Deployment (after both parts are approved and merged)

1. Build graphs on the Mac (`scripts/transit/build_graphs.sh`), rsync to the Pi, install/enable the OTP unit (private runbook).
2. Set `GATEKEYP_OTP_URL=http://127.0.0.1:8080` in `/opt/gatekeyp/.env`; restart the app.
3. Smoke: one plan per region from the Pi; a real event page in each region; OTP-down fallback.
4. Append the deploy to `.audit/gatekeyp-deploy.tsv` in the main checkout.
