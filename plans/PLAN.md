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
