# Transit directions — design

Date: 2026-10-24
Status: draft (awaiting builder check and user approval)
Scope: attendee-facing transit directions on standard and lite event pages,
plus an event start date/time on standard events.
Related: `2026-10-19-privacy-preserving-directions-map-design.md` (the map
card and Open map button this builds on).

## 1. Intent

Attendees currently get a map card and one "Open map" link, but when they
actually travel they fall back to Apple/Google Maps for **transit
directions** — especially the common case of train/bus plus walking. The
goal is a static, reopenable itinerary computed by the Pi: the attendee
enters a start address, receives a walk → transit → walk itinerary with
lines, stops and times, and can return to it for reference during the trip.
No geolocation tracking, no live navigation, no stored origins.

The second, smaller goal: standard events gain an optional **start
date/time** (the lite flyer form has had a When field all along), shown on
the event surfaces. Directions use "depart now" in this version; the date
is informational and becomes the anchor for a later "arrive by" mode.

## 2. What exists today

- `events.location_geo` holds encrypted `{lat, lon}` (geocoded via
  Nominatim at creation or when the map is toggled on); `show_map` controls
  the map card. The map card renders on the attendee event page
  (`renderEventPage`) and the lite page (`/i/{id}`).
- The map widget lazy-loads MapLibre on tap; the card is followed by an
  "Open map" button (OpenStreetMap) and an attribution line.
- Lite events store their schedule (`when`) as a gated content block; the
  lite form's `#flyer-when` is a required `datetime-local`.
- Standard events have no date/time field anywhere.
- The Pi: Raspberry Pi 5, 8 GB RAM (~6.3 GB available), 18 GB free disk,
  4 cores; the app lives in `/opt/gatekeyp` (53 MB).
- Geocoding: `src/core/geocoding.py` `NominatimGeocoder` (cached,
  rate-limited, no address logging on failure). Event creation uses it
  server-side.
- Rate limiting: `src/api/gateway.py` `RateLimiter`, per IP.

## 3. Goals

1. A "Directions" form under the map card on the attendee event page and
   the lite page: start address input → static itinerary.
2. Itinerary shows total time, departure/arrival times, and legs: walk
   (duration/distance) and transit (agency, line, headsign, board/alight
   stops, stop count, times). At most three alternatives; the first is
   expanded.
3. The itinerary is computed on the Pi and **not persisted or logged**;
   the browser keeps the last result in `localStorage` for reference.
4. Works for events in NYC, LA, and Montreal; the region is chosen from the
   event's venue coordinates. New regions are config + data, no code.
5. Standard events gain an optional start date/time, displayed on the
   attendee page, RSVP funnel, and workspace.
6. Feature is off unless configured (`GATEKEYP_OTP_URL` empty = no form),
   so a deploy without routing data stays healthy.

## 4. Non-goals

- Live turn-by-turn navigation, blue-dot positioning, geolocation, service
  alerts, real-time vehicle positions.
- Storing itineraries, origins, or start addresses server-side (no DB rows,
  no audit records, no access-log bodies).
- Self-hosted geocoding (accepted: start addresses go to Nominatim).
- Car/bike routing; walking-only routes as a first-class mode (walk legs
  are part of transit itineraries).
- Drawing the route line on the MapLibre card (phase 2).
- Arrive-by planning, timezone conversion across regions, multi-day trips.

## 5. Anti-goals (failure conditions)

- A start address or origin coordinate appears in any log, audit row,
  error message, or database row.
- The event URL or key leaks to Nominatim, OTP, or any third party via
  Referer (the existing `no-referrer` policy stays).
- Event creation or the map card breaks when OTP/GTFS data is missing or
  stale.
- Directions are available for ended/decommissioned events.

## 6. Decisions made with the user

- The **Pi computes routes**; the host accepts transiently seeing origins
  and discards them.
- A **geocoding hop to a trusted third party** (Nominatim) is acceptable.
- Directions default to **"depart now"**; the event date/time is added to
  standard events as a companion change.
- Static itinerary for reference is sufficient; no location tracking.

## 7. Architecture

### 7.1 Event start date/time (companion change)

- `events.starts_at TEXT` added via `_ensure_column` (additive migration).
  Stores the `datetime-local` string verbatim (naive local time; the venue
  timezone is unknown). Blank = unset.
- `CreateEventRequest.starts_at: str | None` (max 64), passed through
  `EventLifecycleManager.create_event` → `add_event`. Optional at the API
  level so existing clients/tests stay valid.
- SPA create form gains a `datetime-local` field (required in the form,
  matching the lite form's When). Validation: parseable ISO datetime-local.
- Display when set: attendee event page (under the lede), RSVP funnel,
  workspace header. Formatting: short local format, no timezone suffix.
- Lite `when` stays as-is (gated content block); the lite page already
  shows it.

### 7.2 Routing service (OTP)

- **OpenTripPlanner 2.x** as a separate systemd service on the Pi:
  loopback only (`127.0.0.1:8080`), `-Xmx3g`, restart on failure, no public
  exposure. nginx never proxies it.
- One OTP instance with three graphs: `nyc`, `la`, `mtl` (OTP multi-graph,
  selected per request by router id). If memory pressure makes three
  simultaneous graphs unsafe, fall back to loading only the regions with
  live events (ops switch, same API).
- Query: GTFS GraphQL `plan` (OTP 2.x), `modes = WALK,TRANSIT`,
  `numItineraries = 3`, `dateTime = now`, `arriveBy = false`.
- Router selection: venue coordinates → configured bbox per region. No
  match → directions unavailable (fallback message + Open map).
- Region config (env, JSON): id, bbox, GTFS attribution string, OTP router
  id. Defaults shipped for NYC/LA/MTL; unknown regions are ignored.

### 7.3 Data pipeline (off-box)

- Build on the Mac (the Pi's 4 cores/8 GB are not a build machine):
  download GTFS zips (MTA subway/bus/LIRR/Metro-North; LA Metro + Metrolink;
  STM + exo + REM), download OSM metro extracts (BBBike/Geofabrik), run
  `otp --build --save` per region, then `rsync` the graphs to the Pi and
  restart OTP.
- Refresh cadence: GTFS monthly (or when feeds change), OSM quarterly.
  Documented in the private lichen-site runbook (server access stays out of
  the public repo); the build script itself can live in the public repo.
- Attribution: show the region's transit-data credit (e.g. "Transit data ©
  MTA") under the itinerary; OSM/OpenMapTiles attribution stays on the map.
- Size budget (estimates): GTFS ~0.2–0.3 GB, OSM metro PBF ~1.1–1.5 GB,
  OTP graphs ~3–4 GB, all three regions. Disk 18 GB free — fine. JVM heap
  3 GB cap; graphs must fit or the region set is trimmed.

### 7.4 API

`POST /api/directions`

Request:
```json
{ "event_id": "event_…", "start": "123 Main St, Brooklyn", "key": "local:…" }
```
- `key` is required for standard events (an access key that grants the
  event) and omitted for lite events (public by design).
- Validation: event exists and is live (not ended/decommissioned); start
  non-empty, max 256 chars; rate limit per IP (default 10/min, configurable).
- Flow: verify event → venue coordinates must exist → geocode `start` with
  `NominatimGeocoder` in **no-cache mode** (attendee origins are never
  retained; the existing 24 h address cache is bypassed on this path) and a
  **soft viewbox bias** to the event's region (`bounded=0`, so a genuine
  long-distance origin still resolves) → pick router by venue bbox → OTP
  plan → map to the compact response. Nothing is persisted.

Response (200):
```json
{
  "event_id": "event_…",
  "origin": {"label": "123 Main St, Brooklyn", "lat": 40.70, "lon": -73.95},
  "destination": {"label": "Venue address", "lat": 40.75, "lon": -73.98},
  "depart_at": "2026-10-24T18:30:00-04:00",
  "arrive_at": "2026-10-24T19:05:00-04:00",
  "duration_minutes": 35,
  "legs": [
    {"mode": "WALK", "minutes": 4, "distance_m": 300, "from": "Origin", "to": "Bedford Av"},
    {"mode": "TRANSIT", "agency": "MTA", "line": "L", "headsign": "Canarsie",
     "color": "#…", "stops": 3, "depart": "…", "arrive": "…",
     "from_stop": "Bedford Av", "to_stop": "1 Av"},
    {"mode": "WALK", "minutes": 6, "distance_m": 450, "from": "1 Av", "to": "Venue"}
  ],
  "attribution": "Transit data © MTA"
}
```
Times are ISO 8601 carrying the venue region's UTC offset; the UI displays
them in **venue-local time** (the region config carries the timezone), so
an out-of-town viewer is never shown a shifted departure. A past
`starts_at` does **not** close directions — "ended" means decommissioned/
tombstoned (standard) or expired (lite) only.
Errors: `400` bad input; `403` key does not grant the event; `404` unknown
or ended event; `422` geocode failed / no route; `503` OTP or data
unavailable. Error bodies never echo the start address.

### 7.5 Frontend

- Under the map card (both surfaces): a compact form — label "From", text
  input, submit "Get directions". Only rendered when directions are
  configured for the event's region, `show_map` is true (the toggle is the
  organizer's location-data consent switch), and venue coordinates exist.
  Turning the map off hides both the card and directions; coordinates stay
  encrypted so turning it back on restores both without re-geocoding. No
  backfill: events created with the map off have no coordinates and never
  show directions.
- Result: total duration and departure/arrival times; up to three
  alternatives as expandable rows; legs as a terse list (walk / line +
  headsign / board–alight / times). No helper prose (§3.4), no map drawing.
- Persistence: last successful result + start text in `localStorage` under
  `gatekeyp.directions.<event_id>`; restored on load with a "Clear" action.
- Failure: a single terse line ("No transit route found." / "Directions
  unavailable right now.") plus the existing Open map button; the map card
  and links always keep working.
- `no-referrer` and the existing CSP-less setup stay unchanged; the form
  does not request geolocation.

### 7.6 Privacy boundary

- Origin: sent by the browser to the Pi over the existing HTTPS origin; the
  Pi geocodes it via Nominatim (trusted third party) and sends it to the
  local OTP instance. No other party sees it.
- No logging: the directions route must not log request bodies; the audit
  logger must not record the start; uvicorn access logs record the path,
  not the body (verify in review). OTP's request log is disabled.
- No storage: no DB writes; no itinerary cache server-side. The browser may
  keep the result locally.
- Threat model gains: "the host can transiently observe attendee origins;
  they are discarded, not logged" and the Nominatim hop.
- Rate limiting protects the public lite surface from abuse.

## 8. Constraints

- Pi memory: OTP heap ≤ 3 GB, app + YunoHost + OS must keep ≥ 1 GB free.
- Graph builds happen off-box; the Pi only stores and serves graphs.
- No new third-party request at page load; the directions call happens only
  on submit.
- GTFS feed licenses: static feeds only, attribution per region; no
  real-time feeds in v1.
- Design system: dark-only, terse copy, no helper paragraphs.

## 9. Failure modes

| Situation | Behaviour |
|---|---|
| `GATEKEYP_OTP_URL` empty | No directions form; map card + Open map unchanged |
| Venue has no coordinates | No form; Open map search link only |
| `show_map` false (even with coordinates) | No form; map card hidden; Open map link remains |
| Region not configured | No form for that event |
| Nominatim fails | 422 "Could not find that address."; form stays |
| OTP down / timeout (5 s) | 503 "Directions unavailable right now."; Open map stays |
| No route | 422 "No transit route found."; Open map stays |
| Event ended/decommissioned | 404; form hidden on the next render |
| Rate limited | 429 with Retry-After; terse message |

## 10. Testing

- Unit: bbox → router selection; OTP GraphQL response → itinerary mapping
  (recorded fixtures); endpoint validation (unknown/ended event, bad key,
  rate limit, geocode failure, OTP failure); assertion that the start
  address never appears in audit/log records; event `starts_at` round-trip
  and display.
- E2E: a local mock OTP HTTP server (same pattern as the mock Nominatim
  fixture); standard event: fill start → itinerary legs/times render;
  lite page: same; OTP failure → terse fallback and Open map still works;
  no request before submit; localStorage restore; ended event → form gone.
- Ops: graph build is not in CI; a smoke script checks the OTP health
  endpoint and a sample plan on the Pi after each data refresh.

## 11. Rollout

1. Companion change: `starts_at` (schema, API, form, display) — ship first,
   independent.
2. Build graphs for NYC/LA/MTL on the Mac; install OTP on the Pi; verify a
   sample plan per region.
3. Ship the API + UI behind `GATEKEYP_OTP_URL`; enable per environment.
4. Update the threat model, design system note (terse itinerary list),
   README (env vars), roadmap (routing checkbox), and the private runbook
   (data refresh).

## 12. Builder-check outcomes

Settled as builder calls (recorded here so they can be reviewed):

- **No origin retention:** the directions path bypasses the geocoder's 24 h
  address cache (no-cache mode) — attendee origins exist only for the
  request.
- **Times:** displayed in venue-local time (region config carries the
  timezone); ISO responses carry the offset.
- **"Ended":** decommissioned/tombstoned (standard) or expired (lite) only;
  a past `starts_at` does not close directions.
- **Geocoding bias:** soft viewbox to the event's region, `bounded=0`.
- **Feeds:** static GTFS feeds for MTA, LA Metro/Metrolink, STM/exo/REM are
  expected to be public downloads; the plan verifies each URL and its
  attribution text before the graph build, and treats any registration
  requirement as a rollout prerequisite.

Open for the user:

- **Resolved:** the map toggle is a **location-data opt-out**. If it is off
  at creation, the venue is never geocoded; if it is off later, the
  directions form is hidden (coordinates stay encrypted for a later
  re-enable). No backfill for existing map-off events.
