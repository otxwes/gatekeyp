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
