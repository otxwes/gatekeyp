# Plan — Organizer-controlled invite card style

Approved by the user 2026-11-08. The organizer sets one invite-card style per
event in the RSVP funnel tab. Every attendee card — RSVP-submitted, single
generated, and bulk generated — uses it. Attendees never see a cover picker.
The organizer's own card keeps its picker and defaults to the event style.
The style is editable at any time; it applies to cards generated after the
save. Already-downloaded cards keep their pixels (the raw key exists only
inside the card).

## Decisions

- **Option B:** presets + event flyer + a dedicated card image upload. The
  dedicated image is stored as an event media asset and served on a public
  `rsvp/card-cover` route. It is not shown as the funnel poster.
- **Option 1:** one style for all attendee cards. The Access keys tab stops
  asking for a cover; single and bulk cards use the event style. The bulk
  "random per key" cover option goes away. The organizer's own card keeps its
  picker.
- Storage: `events.card_style` JSON — `{"type":"none"}`, `{"type":"preset",
  "id":"hatch"}`, `{"type":"flyer"}`, or `{"type":"image","asset_id":"…"}`.
- The `flyer` style is dynamic: changing the event flyer changes the card art
  for new cards. The `image` style is a fixed asset.
- Public view returns a normalized style. `image` carries a URL to the public
  card-cover route. Missing flyer/asset falls back to `none`.

## Global constraints

- Run from the repo root. Python via `uv`.
- Verify every task; the full gate is:
  `uv run pytest -q`, `uv run pytest tests/e2e -m e2e -q`,
  `uv run ruff check src tests`, `node --check web/app.js`.
- Keep the existing monochrome design system and the cards-only/stego
  security model: no key material in the style, the public card-cover route,
  or any log.
- The organizer's own card and the lite-event creation card keep their
  existing picker; only attendee cards become locked to the event style.

## Task 1: Add the card_style column and media metadata helper

**Files:** `src/db/database_handler.py`, `tests/test_database_handler.py`

**Steps (RED → GREEN):**

1. Add failing tests:
   - A legacy events table gains a `card_style` column after migration.
   - `add_event` + `get_event` round-trips `card_style` as `None` by default.
   - `set_rsvp_card_style` stores JSON and `get_event` returns it.
   - `get_media_asset_meta` returns metadata without the blob and `None` for
     an unknown id.
2. Run `uv run pytest tests/test_database_handler.py -q`; the new tests fail.
3. Implement:
   - `_EVENT_CARD_STYLE_MIN_COLS = 22`; add `card_style TEXT` at the end of the
     `events` CREATE TABLE; `_ensure_column("events", "card_style", "TEXT")`.
   - `get_event` returns `"card_style": result[22] if len(result) > 22 else None`.
   - `set_rsvp_card_style(event_id, style_json)` updates the column.
   - `get_media_asset_meta(asset_id)` selects id/event_id/filename/mime_type/
     size_bytes/created_at (no `data`, no decryption).
4. Re-run the test file; all green.
5. Commit: `feat(db): store the event card style`.

**Test command:** `uv run pytest tests/test_database_handler.py -q`

## Task 2: Service validation, settings, public view, cover asset

**Files:** `src/rsvp/service.py`, `tests/test_rsvp.py`, `tests/card_ref.py`

**Steps (RED → GREEN):**

1. Add failing tests:
   - `get_rsvp_settings` returns `card_style: {"type":"none"}` and
     `flyer_asset_id: None` by default.
   - `update_rsvp_card_style` accepts none/preset/flyer/image and returns the
     normalized style.
   - Rejects an unknown type, an unknown preset, `flyer` with no flyer,
     `image` with a missing/foreign/non-image asset, and a wrong organizer key.
   - `get_public_view` includes the style; `flyer`/`image` fall back to `none`
     when the referenced asset is gone.
   - `get_card_cover_asset` returns the asset bytes for an image style and
     raises not-found for none/preset/flyer.
   - A test pins `CARD_COVER_PRESETS` to
     `tests.card_ref.COVER_PRESET_IDS - {"none"}`.
2. Run `uv run pytest tests/test_rsvp.py -q`; the new tests fail.
3. Implement in `src/rsvp/service.py`:
   - `CARD_COVER_PRESETS = ("hatch","keyline","dots","keyhole")` and style-type
     constants.
   - `_parse_card_style(raw)` — fail-safe parse, unknown → none.
   - `_public_card_style(event)` — normalize; flyer requires an existing
     image asset on the event; image requires an existing image asset owned by
     the event and returns `{"type":"image","url":"/api/events/{id}/rsvp/card-cover"}`.
   - `get_rsvp_settings` adds `card_style` + `flyer_asset_id`.
   - `update_rsvp_card_style(organizer_key, event_id, style)` validates and
     stores canonical JSON, returns `{"event_id", "card_style"}`.
   - `get_public_view` adds `card_style` to `event`.
   - `get_card_cover_asset(event_id)` verifies live event + image style +
     owned asset and returns the decrypted asset dict.
4. Re-run; all green.
5. Commit: `feat(rsvp): validate and expose the event card style`.

**Test command:** `uv run pytest tests/test_rsvp.py -q`

## Task 3: HTTP routes and wiring

**Files:** `src/rsvp/routes.py`, `tests/test_rsvp.py`, `tests/test_api_server.py`

**Steps (RED → GREEN):**

1. Add failing route tests:
   - `POST /api/events/{id}/rsvp/card-style` round-trips a preset and returns
     400 for invalid styles and wrong keys.
   - `GET /api/events/{id}/rsvp/card-cover` serves image bytes with
     `inline`, `public, max-age=86400`, ETag, `nosniff`; 404 when absent;
     410 after wipe; 404 unknown event.
   - Both profiles register the two new paths.
2. Run `uv run pytest tests/test_rsvp.py tests/test_api_server.py -q`; fail.
3. Implement:
   - `RsvpCardStyleRequest` with `organizer_key` + `style: dict`.
   - POST handler maps `RsvpValidationError` → 400, `RsvpNotFoundError` → 404.
   - GET card-cover handler maps not-found → 404, gone → 410; mirrors the
     flyer headers.
   - Update the route-inventory sets in the tests.
4. Re-run; all green.
5. Commit: `feat(rsvp): add card-style and card-cover endpoints`.

**Test command:** `uv run pytest tests/test_rsvp.py tests/test_api_server.py -q`

## Task 4: Web card-style helper and locked cover modal

**Files:** `web/app.js`, `tests/test_invite_card_cover.py`

**Steps (RED → GREEN):**

1. Add failing static tests in `tests/test_invite_card_cover.py`:
   - `coverFromCardStyle` exists and maps none/preset/flyer/image.
   - `openCardCoverModal` accepts a locked cover (the `lockedCover` marker)
     and the attendee result passes it.
2. Run `uv run pytest tests/test_invite_card_cover.py -q`; fail.
3. Implement in `web/app.js`:
   - `coverFromCardStyle(style, eventId)` → renderer cover object.
   - `openCardCoverModal(card)`:
     - initialize `cover` from `card.cover` or none;
     - load an initial image cover before the preview;
     - if `card.lockedCover`, omit the cover chips/upload and render only the
       note + preview + download/save;
     - keep the iOS share flow, fresh-key lock, and organizer note.
4. Run the static test + `node --check web/app.js`; green.
5. Commit: `feat(web): add locked card covers and style mapping`.

**Test command:** `uv run pytest tests/test_invite_card_cover.py -q`

## Task 5: RSVP funnel tab and attendee flow

**Files:** `web/app.js`, `tests/e2e/pages.py`, `tests/e2e/test_rsvp_flow.py`, `tests/e2e/test_rsvp_flyer.py`

**Steps (RED → GREEN):**

1. Add a failing E2E test (or extend `test_rsvp_flyer.py`) that:
   - opens the organizer RSVP tab;
   - selects a preset, saves, and sees the saved chip selected after reload;
   - has an attendee RSVP and asserts the card modal has no `.cover-chip`,
     `#card-preview` is visible, and the public view carries the style.
2. Add a `set_card_style` helper to `OrganizerPage` and an assertion helper to
   `AttendeePage`.
3. Run the new test; fail (UI missing).
4. Implement in `web/app.js`:
   - `wsRsvps`: fetch `card_style` + `flyer_asset_id` from the settings GET;
     render an "Invite card" section (chips: None/Hatch/Keyline/Dots/Keyhole/
     Flyer if set/Own image…, live 200×300 preview, "Save card style").
   - On save: upload a local image first via the existing media endpoint, then
     POST `/rsvp/card-style`; refresh the preview and show a toast/note.
   - `showRsvpResult`: map `event.card_style` with `coverFromCardStyle` and
     open the modal with `lockedCover: true`.
5. Run the E2E test; green. `node --check web/app.js`.
6. Commit: `feat(web): let organizers set the RSVP invite-card style`.

**Test command:** `uv run pytest tests/e2e/test_rsvp_flow.py tests/e2e/test_rsvp_flyer.py -m e2e -q`

## Task 6: Access keys and organizer card default

**Files:** `web/app.js`, `tests/e2e/test_organizer_flows.py`, `tests/e2e/test_card_save_share.py`

**Steps (RED → GREEN):**

1. Update/add failing E2E tests:
   - Single and bulk key generation show no cover chips and download a card
     using the event style.
   - The organizer's own card modal still offers the flyer chip.
2. Run the affected tests; fail where the UI still shows the bulk picker.
3. Implement in `web/app.js`:
   - `wsKeys`: fetch the RSVP settings; compute the event cover; single key
     modal uses `lockedCover: true`; bulk downloads use the same cover.
   - Remove the bulk "Card cover" select/picker and `randomCoverPreset`.
   - `#ws-organizer-card`: fetch the settings, preselect the event style, keep
     the picker.
4. Run the affected E2E tests; green. `node --check web/app.js`.
5. Commit: `feat(web): use the event card style for generated keys`.

**Test command:** `uv run pytest tests/e2e/test_organizer_flows.py tests/e2e/test_card_save_share.py -m e2e -q`

## Task 7: Full E2E coverage for the new flows

**Files:** `tests/e2e/test_rsvp_flyer.py`, `tests/e2e/test_rsvp_flow.py`, `tests/e2e/pages.py`

**Steps:**

1. Add tests for:
   - a custom card image upload → public card-cover 200 + attendee card;
   - changing the style later → a later RSVP gets the new style;
   - the public view fallback after the flyer/asset is removed (if practical
     through the UI).
2. Run `uv run pytest tests/e2e -m e2e -q`; fix any regressions.
3. Commit: `test(e2e): cover organizer-controlled invite cards`.

**Test command:** `uv run pytest tests/e2e -m e2e -q`

## Task 8: Docs and full verification

**Files:** `README.md`, `docs/steganography_invites.md`, `docs/threat_model.md`, `roadmap.md`, `docs/project_memory.md`

**Steps:**

1. Update the README invite-card description (organizer-controlled style, no
   attendee picker, dedicated card art).
2. Update `docs/steganography_invites.md`: replace the "no new server surface"
   claim with the card-style endpoint + public card-cover route; note the
   image is public while the event is live.
3. Update `docs/threat_model.md`: card art is public (like the flyer), carries
   no key material, 410 after wipe.
4. Add the phase/decision note to `roadmap.md` and
   `docs/project_memory.md`.
5. Run the full gate:
   - `uv run pytest -q`
   - `uv run pytest tests/e2e -m e2e -q`
   - `uv run ruff check src tests`
   - `node --check web/app.js`
6. Commit: `docs: document organizer-controlled invite cards`.

**Test command:** `bash -lc "uv run pytest -q && uv run ruff check src tests && node --check web/app.js"`

## Review Focus

- The public card-cover route must never expose key material and must 410
  after a wipe.
- The style fallback must be safe when the flyer or image asset disappears.
- No attendee surface may show cover chips; the organizer card and lite
  creation flows keep theirs.
- Existing cards and the stego payload format are untouched.
- The `flyer` style is dynamic; the `image` style is a fixed asset.
- Legacy databases migrate cleanly; `get_event` column guards stay correct.
