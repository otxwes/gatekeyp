# Privacy-preserving directions map — design

Date: 2026-10-19
Status: proposed (awaiting builder check and user approval)
Scope: attendee-facing directions widget on standard and lite event pages.
Surveillance recon is a separate future project.

> **Amendment (2026-10-23, user-approved):** the link row is now a single
> OpenStreetMap link; Organic Maps, OsmAnd, and "Copy address" were removed as
> redundant (the address is already shown above the card). The map card, its
> attribution line (license requirement), and the OSM-search fallback for
> un-geocoded addresses are unchanged.

## 1. Intent

Today the event address appears only on the unlocked standard event page
(`renderEventPage`) and the public lite share page (`/i/{event_id}`). The address
is free text, so the attendee has to copy it into whatever map app their phone
defaults to, which is usually Apple Maps or Google Maps. We want a small map that
works without corporate maps, plus links that hand off to open-source navigation
apps.

The second motivation is the organizer's later surveillance-recon workflow: an
underground event may need custom directions, or a different venue, if there are
known cameras on the route. That feature is out of scope here, but it needs event
coordinates. This design introduces the coordinate foundation (geocoded once,
encrypted at rest) that the recon view can reuse. The recon view will be
organizer-only; camera data must never be rendered on the attendee page.

## 2. Goals

- Show a small interactive map of the event location on:
  - the unlocked standard event page (`#/join` attendee view);
  - the public lite event page (`/i/{event_id}`).
- Load the map only after the attendee taps "Show map". No third-party map
  request on page load.
- Provide links to OpenStreetMap, Organic Maps, and OsmAnd, plus "Copy address".
- Geocode the free-text address once, at event creation, via Nominatim. Store the
  result encrypted at rest. Do not geocode on page views.
- Add a per-event "Map" switch (default on), set at creation and changeable
  later from the standard organizer workspace, so an organizer can remove the
  map widget for a high-risk event. Links remain.
- Keep the Raspberry Pi load negligible: the Pi serves vendored static JS/CSS and
  the event page; map tiles go directly from the attendee's browser to
  OpenFreeMap. No tile proxy, no server-side image rendering, no per-view
  geocoding.
- Set `Referrer-Policy: no-referrer` globally so event URLs, and any future
  URL-borne keys, cannot leak through map or outbound-link requests.
- Reuse the same map stack later for the organizer recon overlay.

## 3. Non-goals

- Turn-by-turn routing or geofencing. OpenFreeMap does not provide routing; the
  app links hand off to navigation apps.
- Live location, "locate me", or geolocation permission.
- Surveillance-camera data, recon UI, or any camera overlay. Separate project.
- A map on the public RSVP request page. That page never shows the address.
- A map on the organizer workspace. The organizer already knows the location;
  recon will add its own map.
- A location picker or draggable pin at event creation. v1 uses forward
  geocoding only. The recon project may add a pin.
- Editing an event's address or coordinates after creation. The Map switch is
  editable; the location itself is not.
- A lite-profile organizer settings page. The post-creation toggle lives in the
  standard organizer workspace; lite-profile deployments (which mount only the
  ephemeral routes) keep the create-time switch.
- Backfilling coordinates for existing events. Existing events keep working; the
  map is absent, links fall back to an address search.
- Offline maps or self-hosted tiles. OpenFreeMap is self-hostable later if the
  organizer wants zero third-party tile requests.
- A static map image, server-side tile composition, or a tile proxy. Those are
  heavier on the Pi and are explicitly rejected.

## 4. Constraints

- Pi: low CPU/bandwidth; no new heavy Python dependencies; no server-side map
  rendering.
- Web app: zero-build vanilla JS. Vendor MapLibre; do not add a bundler or CDN.
- Dark-only design system; terse copy, no helper paragraphs (design-system §3.4).
- Event location is high-sensitivity data: encrypted at rest, returned only to a
  valid key on the standard path. The lite path already publishes when/where by
  design.
- Existing additive migration pattern via `_ensure_column`.
- Tests: unit + e2e, ruff clean, `node --check`.

## 5. User experience

### 5.1 Standard event page (unlocked)

After the existing address line, if the event has coordinates, `show_map` is
true, and a map style is configured:

- A map card, roughly 100% wide and 200px tall, with a CSS-only placeholder
  (dotted ground, a pin, a "Show map" button).
- A visible attribution line: "OpenFreeMap · © OpenMapTiles · Data from
  OpenStreetMap", with links to openfreemap.org, openmaptiles.org, and the OSM
  copyright page. This matches OpenFreeMap's quick-start attribution and
  satisfies the OpenMapTiles and OSM requirements.
- A terse link row: OpenStreetMap · Organic Maps · OsmAnd · Copy address.
- Tapping "Show map" replaces the placeholder with an interactive MapLibre map
  centered on the coordinates at zoom 16, with a single marker. Cooperative
  gestures, no rotation/pitch, no geolocation control, one small zoom control.
- If the map fails to load, the placeholder stays and the button becomes
  "Map unavailable" (disabled). The links remain.
- If `show_map` is false: no map card, no "Show map". The link row still appears
  if coordinates exist; if not, an OSM search link plus Copy address.
- If the event has no address: no map and no links.

### 5.2 Lite event page (`/i/{event_id}`)

The lite share page already publishes when/where by design. Same map card and
link row as 5.1, server-rendered, using the same `map_widget.js`. The map is
public on this page; the per-event switch still lets the organizer remove it.
The page includes the no-referrer meta tag.

### 5.3 Create forms

- Standard "New gathering" form: a "Map" checkbox after the Location field,
  checked by default. The JSON create request carries `show_map`.
- Lite flyer form: a "Map" checkbox after the Where field, checked by default.
  The form uses a hidden `show_map=0` before the checkbox `show_map=1` so an
  unchecked box posts `0`.
- If `show_map` is off, the server does not geocode the address and does not
  send it to Nominatim.
- If the map is on and geocoding fails, the event is still created. The create
  response carries `map_available: false`. `map_available` is true only when the
  event has stored coordinates, `show_map` is true, and a map style is
  configured. The SPA shows a terse toast "Event created. Map unavailable." only
  when `show_map` is true, the address is non-empty, and `map_available` is
  false; the lite result panel uses the same condition. The links still work via
  OSM search.

### 5.4 Map states

| Address | show_map | Coordinates | Map card | Links |
|---|---|---|---|---|
| none | any | none | no | no |
| present | off | not geocoded | no | OSM search + Copy address |
| present | on | geocode failed | no | OSM search + Copy address |
| present | on | geocoded | placeholder → interactive on tap | OSM, Organic Maps, OsmAnd, Copy address |
| present | off | geocoded | no | OSM, Organic Maps, OsmAnd, Copy address |

With `show_map` off we do not geocode new events, so the "off + geocoded" row
applies to an event whose map was turned off after creation (the coordinates
are kept) or to an event created before the switch existed. The links can use
the stored coordinates if present.

### 5.5 Organizer workspace toggle

The standard workspace header shows a terse "Map" checkbox next to the location
line, only when the event has an address. It reflects the current `show_map`.
Changing it calls `POST /api/events/{event_id}/map` with
`{organizer_key, show_map}` and updates the checkbox from the response.

- Turning the map off sets `show_map=0` and keeps `location_geo`. The attendee
  and lite pages drop the map card on their next load; the links remain.
- Turning it on with stored coordinates re-enables the map without another
  geocode.
- Turning it on without coordinates (the event was created with the map off, or
  the first geocode failed) makes the server geocode the address at toggle time
  and store the result. If geocoding fails, `show_map` stays on but
  `map_available` is false; the workspace shows "Map unavailable." Toggling off
  and on retries.
- The endpoint returns 400 when asked to enable a map for an event with no
  address. The checkbox is not rendered in that case.
- Lite-profile deployments have no workspace, so their events keep the
  create-time switch. A full-profile workspace can toggle a lite event created
  on that instance.

## 6. Data model

Add two columns to `events`:

- `location_geo TEXT` — nullable, encrypted JSON
  `{"lat": <float>, "lon": <float>}`.
- `show_map INTEGER NOT NULL DEFAULT 1` — 1/0.

Column order matters because `get_event` reads by position. Add
`organizer_name TEXT`, `location_geo TEXT`, and
`show_map INTEGER NOT NULL DEFAULT 1` to the `CREATE TABLE events` definition
in that order after `slug`, so a fresh database gets indices 12, 13, 14. In
`_migrate_schema`, call `_ensure_column` for `organizer_name` first (already
present in current databases), then `location_geo`, then `show_map`; legacy
databases that already have `organizer_name` at index 12 get the new columns at
13 and 14. Existing rows get `show_map=1` and `location_geo=NULL`.

`DatabaseHandler.add_event` gains `location_geo: str | None = None` and
`show_map: bool = True`. It encrypts `location_geo` with `_encrypt` (same as
`location_data`) and stores `1`/`0`.

`DatabaseHandler.get_event` returns:

- `location_lat: float | None`
- `location_lon: float | None`
- `show_map: bool`

It decrypts `location_geo`, parses the JSON, and returns `None` for both
coordinates if the field is absent or malformed. A decryption failure follows
the existing `location_data` behavior (`DecryptionError`); a malformed JSON
payload logs a warning without the address and returns `None` so the event page
still works. Positional guards: `_EVENT_LOCATION_GEO_MIN_COLS = 13`,
`_EVENT_SHOW_MAP_MIN_COLS = 14`.

`DatabaseHandler.set_event_location_geo(event_id, location_geo: str | None)`
updates and encrypts the geo field; used by the lite service after geocoding and
by the toggle-on path.

`DatabaseHandler.set_event_show_map(event_id, show_map: bool)` updates the
switch. The lifecycle's `set_event_map(organizer_key, event_id, show_map)`
verifies the organizer key with the same check as `get_event_details`, geocodes
when enabling without stored coordinates, writes both fields, and returns
`{show_map, map_available}`.

The public RSVP view (`RsvpService.get_public_view`) does not include
coordinates, `show_map`, or the map style. The lite public view
(`EphemeralService.get_public_view`) includes them because the lite page
publishes the location. The lite keyed view used for LXMF delivery does not need
them.

## 7. Geocoding

New module `src/core/geocoding.py`:

- `GeoPoint(lat: float, lon: float)`.
- `NominatimGeocoder(base_url, user_agent, timeout=3.0, cache_ttl=86400,
  max_cache=256)`.
- `geocode(address: str) -> GeoPoint | None`.
- Uses stdlib `urllib.request` (no new runtime dependency) with
  `format=jsonv2&limit=1`, a valid `User-Agent`, a 3s timeout, and an in-memory
  cache keyed by the normalized address (whitespace-collapsed, lowercased).
  Positive results are cached for 24h; failures are not cached.
- A module-level lock enforces at most one request per second (Nominatim
  policy). The lock is per process.
- Failures (timeout, HTTP error, bad JSON, no result) return `None` and log a
  warning without the address or coordinates.
- The geocoder is injectable (protocol or simple class with `geocode`); tests
  use a fake.

Config (read in `create_app` / `_build_lite_app`):

- `GATEKEYP_MAP_STYLE_URL` — default
  `https://tiles.openfreemap.org/styles/dark`. Empty string disables maps and
  geocoding entirely.
- `GATEKEYP_GEOCODER_URL` — default `https://nominatim.openstreetmap.org`.
  Empty string disables **new** geocoding only; events that already have stored
  coordinates still render the map when `GATEKEYP_MAP_STYLE_URL` is set. Links
  remain for everything else.
- `GATEKEYP_GEOCODER_USER_AGENT` — default
  `gatekeyp/0.1 (+https://cellar.otxwes.nohost.me)`.

Geocoding happens only when:

- a map style is configured,
- a geocoder is configured,
- `show_map` is true,
- the event has a non-empty address.

Standard path: `EventLifecycleManager.create_event` geocodes `location_data`
before `add_event`, passes `location_geo` and `show_map` to `add_event`, and
returns `map_available`.

Lite path: `EphemeralService.create_event` geocodes `where` (after validation,
before or after `lifecycle.create_event` as convenient), calls
`set_event_location_geo`, and returns `map_available`. `show_map` is passed
through `lifecycle.create_event` to `add_event`.

Toggle-on path: `EventLifecycleManager.set_event_map` geocodes the event's
`location_data` when `show_map` is being turned on and `location_geo` is absent.
This covers events created with the map off and earlier geocode failures. It is
still a settings-time request, not a page view.

No geocoding on page views, no reverse geocoding, no background jobs.

## 8. Event responses

Standard door response (gateway): the event dict from `get_event` now carries
`location_lat`, `location_lon`, `show_map`. The `Gateway` gets a
`map_style_url` constructor parameter; when it is set and the accessed content is
an event, the gateway adds `map_style_url` **inside the event dict**
(`result.data.map_style_url`), not at the top level, so the SPA's existing
`attendee.event` object carries it. Existing tests that assert exact event dicts
will need the new keys.

Lite public view: add `location_lat`, `location_lon`, `show_map`, and
`map_style_url` **inside `view["event"]`** so `_render_live_page` can render the
widget. The lite page is public by design.

Create responses: add `map_available: bool` to the standard and lite create
payloads. The SPA uses it for the terse failure toast/status.

Toggle endpoint: `POST /api/events/{event_id}/map` with
`{organizer_key: str, show_map: bool}`. Returns
`{show_map: bool, map_available: bool}`. Organizer-key verification matches
`get_event_details`; an invalid key or unknown event follows the existing
lifecycle error path (400). Enabling a map for an event with no address returns
400. Turning the map off always succeeds.

## 9. Map widget

New `web/map_widget.js`, loaded by `web/index.html` before `app.js` and by the
lite page with `defer`. It exposes
`window.GatekeypMap = { mount(el), autoMount() }`.

Markup (both surfaces):

```html
<figure class="event-map" data-gatekeyp-map
        data-lat="..." data-lon="..." data-style="..."
        data-title="..." data-address="...">
  <div class="event-map-canvas"></div>
  <button class="event-map-load" type="button">Show map</button>
</figure>
<p class="event-map-links">
  <a href="..." target="_blank" rel="noopener noreferrer">OpenStreetMap</a>
  <a href="..." target="_blank" rel="noopener noreferrer">Organic Maps</a>
  <a href="..." target="_blank" rel="noopener noreferrer">OsmAnd</a>
  <button type="button" class="linklike" data-copy-address>Copy address</button>
</p>
<p class="map-attribution">
  <a href="https://openfreemap.org" target="_blank" rel="noopener noreferrer">OpenFreeMap</a>
  · <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener noreferrer">© OpenMapTiles</a>
  · Data from <a href="https://www.openstreetmap.org/copyright"
  target="_blank" rel="noopener noreferrer">OpenStreetMap</a>
</p>
```

Behavior:

- `mount(el)` is idempotent. It reads the data attributes; if lat/lon/style are
  missing, it does nothing.
- On the first "Show map" click, it dynamically loads
  `/vendor/maplibre/maplibre-gl.js` and `/vendor/maplibre/maplibre-gl.css` once
  (module-level promise), then initializes the map.
- Map options: center `[lon, lat]`, zoom 16, `cooperativeGestures: true`,
  `dragRotate: false`, `touchPitch: false`, `pitchWithRotate: false`,
  `attributionControl: false` (we render the visible attribution line
  ourselves), one `NavigationControl({ showCompass: false })`.
- One marker at `[lon, lat]`.
- On load failure or `!maplibregl.supported()`, keep the placeholder and set the
  button to "Map unavailable" (disabled). The links stay.
- `autoMount()` mounts every `[data-gatekeyp-map]` on DOMContentLoaded. The SPA
  calls `mount` explicitly after `renderEventPage`; the lite page relies on
  `autoMount`.
- The copy button uses `navigator.clipboard.writeText` with a hidden-textarea
  fallback; it copies the address, not coordinates.
- The widget never requests geolocation, never adds query parameters to
  tile/style URLs, and never logs the address or coordinates.

Links (generated in JS for the SPA and in Python for the lite page; keep the
formats identical):

- OSM: `https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}`
- Organic Maps: `https://omaps.app/map?v=1&ll={lat},{lon}&n={quote(title)}`
- OsmAnd: `https://osmand.net/map/?pin={lat},{lon}#17/{lat}/{lon}`
- No coordinates: OSM search
  `https://www.openstreetmap.org/search?query={quote(address)}`; no app links.

All external links use `target="_blank" rel="noopener noreferrer"`.

Vendoring:

- Put a pinned MapLibre GL JS build in `web/vendor/maplibre/` with its CSS and
  license. No CDN. Record the version and SHA-256 in a short README in that
  directory.
- The exact release/format (UMD vs ESM) is a builder decision; prefer the
  simplest format that works with the zero-build classic scripts. If the chosen
  release only ships ESM, load it with a dynamic `import()` from
  `map_widget.js` and vendor the worker/shared files it needs. The constraint is:
  pinned, local, licensed, no build step.

## 10. Security and privacy

- **No third-party request on page load.** MapLibre, the style, and tiles load
  only after "Show map". The placeholder and attribution line are local.
- **Referrer policy.** Add a `Referrer-Policy: no-referrer` response header in
  `_new_app` for all responses, plus
  `<meta name="referrer" content="no-referrer">` in `web/index.html` and
  `_render_page`. This prevents any event URL (including future URL-borne keys)
  from leaking to OpenFreeMap or to outbound link targets. External links also
  use `rel="noreferrer"`.
- **Provider metadata.** OpenFreeMap/Cloudflare see the attendee IP and the tile
  coordinates (the venue area) when the map is opened. OpenFreeMap's policy says
  no IP logging by default and no cookies; Cloudflare may process requests. This
  is accepted for v1. Self-hosting OpenFreeMap is the future zero-third-party
  option.
- **Per-event and global off switches.** The organizer can turn the map off per
  event; `GATEKEYP_MAP_STYLE_URL=""` disables maps and geocoding globally. With
  the map off, the address is not sent to Nominatim.
- **Coordinates at rest.** `location_geo` is encrypted with the existing Fernet
  key. It is returned only in the key-gated standard event response and on the
  already-public lite page. The public RSVP page never includes it.
- **Supply chain.** Vendored, pinned MapLibre; no CDN; license included. If a CSP
  is added later, allow only the configured style/tile origin plus `blob:`
  workers; no `unsafe-eval`.
- **Client resources.** Lazy load keeps the initial page light. On old devices or
  WebGL failure, the placeholder + links remain. No geolocation permission.
- **Pi load.** The Pi serves the vendored JS/CSS and the event page; tiles go
  browser-to-OpenFreeMap. One geocoding request per event creation (3s timeout,
  cached). No tile proxy, no image compositing, no per-view geocoding.

## 11. Testing

Unit:

- Migration adds `location_geo` and `show_map`; legacy DB upgrade works.
- `add_event` encrypts geo; `get_event` decrypts and returns lat/lon/show_map;
  malformed geo returns None; missing columns default safely.
- Geocoder: success, no result, timeout/HTTP error, cache hit, rate limit, no
  address in logs. Use a fake transport or injectable opener.
- Standard create: geocoder success stores coordinates; failure still creates
  the event with `map_available: false`; `show_map: false` skips geocoding.
- Lite create: same, with `where`; public view includes
  coordinates/show_map/map_style_url; keyed view unaffected.
- API: `CreateEventRequest.show_map` defaults true; false passes through; door
  response includes the new event keys and `map_style_url` when configured; RSVP
  public view excludes them.
- `map_style_url` empty disables geocoding and the map.
- Toggle endpoint: organizer-key auth; off keeps coordinates; on with stored
  coordinates does not geocode; on without coordinates geocodes; geocode failure
  leaves `show_map=1` and `map_available=false`; no-address enable returns 400;
  the attendee and lite views reflect the new value.

E2E:

- Create an event with a location; the event page shows the address, the map
  placeholder, the links, and the attribution. Assert no request to
  `tiles.openfreemap.org` before tapping "Show map".
- Tap "Show map"; intercept the style URL and fulfill a minimal MapLibre style
  with a background layer (no tiles); assert a canvas appears and the
  placeholder button is gone. (Or use a test-only local style; keep third-party
  network out of the suite.)
- The links contain the expected coordinates; the OSM/Organic Maps/OsmAnd hrefs
  are correct; Copy address copies the address.
- Map off: no placeholder, no "Show map"; links still present.
- Workspace toggle: turn the map off; the attendee page drops the map card but
  keeps the links; turn it back on; the placeholder returns. Toggle an event
  created with the map off; the server geocodes and the placeholder appears.
- Geocode failure: no map; OSM search link + Copy address.
- Lite page: placeholder and links render server-side; no-referrer meta present;
  tapping loads the map (same mocked style).
- No-referrer: assert the header on a normal response and the meta tag on
  `index.html` / lite page.
- Regression: public RSVP page has no map or address.

Use a local mock Nominatim for e2e (a tiny HTTP server started by the fixture,
`GATEKEYP_GEOCODER_URL` pointed at it) so tests never call the real service. The
geocoder unit tests cover the real URL construction.

## 12. Documentation and rollout

- `docs/threat_model.md`: add the map/geocoding data flow, the provider metadata
  exposure, the no-referrer mitigation, the per-event/global off switches
  (including the workspace toggle), and the self-hosting note.
- `docs/design_system.md`: one note that the map widget uses a CSS-only
  placeholder, terse links, visible OpenFreeMap/OpenMapTiles/OSM attribution,
  and no helper prose.
- `docs/project_memory.md`: dated entry after implementation with
  what/why/verification.
- `roadmap.md`: Phase 4 note; check off "Select open-source map tiles"
  (MapLibre + OpenFreeMap), leave routing/geofencing and key-level routes
  unchecked.
- README/config docs: list the three env vars and the default/disable behavior.
- No backfill. Existing events keep the address and links; the map appears only
  for newly geocoded events.

## 13. Decisions made (so the builder doesn't re-litigate)

- Interactive client-side map, not a server-rendered static image.
- MapLibre + OpenFreeMap, not Leaflet/raster OSM or an iframe.
- Tap-to-load, not immediate load.
- Per-event switch, default on, changeable later from the standard organizer
  workspace; links remain when the map is off.
- Geocode at creation or when the map is turned on, via Nominatim; no per-view
  geocoding; skip geocoding when the map is off.
- Store coordinates encrypted in `location_geo`; no plaintext columns.
- No map on the public RSVP page or in the organizer workspace (the workspace
  has the toggle, not a map).
- Post-creation Map switch is in scope; location editing is not.
- Lite-profile deployments keep the create-time switch; no lite organizer
  settings page.
- No location picker in v1; forward geocoding only.
- No routing/geofencing; links hand off to apps.
- Recon is a separate, organizer-only project; the attendee page must never show
  camera data.

## 14. Builder decisions left open

- Exact MapLibre release and module format (UMD vs ESM), within the
  pinned/vendored/no-build constraint.
- Dark style choice if OpenFreeMap `dark` is visually incomplete (e.g.,
  `liberty` + a dark treatment), recorded in the docs.
- Exact placeholder CSS and marker styling within the design system.
- Exact placement and data-loading path for the workspace Map toggle (header
  checkbox vs. a settings row), as long as it reflects the current `show_map`
  and only appears when the event has an address.
- Whether to show the geocode-failure toast on the lite result as a toast or a
  status line (terse either way).
- Whether to use `cooperativeGestures` or a tap-to-expand map on small screens
  (must avoid scroll trapping).
- Exact cache size/TTL for the geocoder (defaults above are fine).
