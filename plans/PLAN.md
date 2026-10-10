# Plan — Card-first key UX (no text key display/copy)

(Complete — commit abca97c)

# Plan — Rebrand icon + hide event ID + consolidate board

(Complete — commit 07bda65)

## A. Remove key logo → cellar-appropriate mark
- [ ] `web/index.html` line 9: replace favicon data-URI SVG (key icon → arched doorway)
- [ ] `web/index.html` lines 17-22: replace `.brand-mark` inline SVG (key icon → arched doorway)
- [ ] `src/ephemeral/routes.py` lines 34-39: replace server-side `_FAVICON` (key icon → arched doorway)
- [ ] `web/style.css` lines 303-316: keep `.brand-mark` CSS (fill/stroke unchanged; new SVG is same shape class)
- [ ] Keep invite-card motifs (`keyhole`, `keyline` presets + `drawKeyhole()`) — decorative, not brand

## B. Remove event ID from UI (users don't need internal metadata)
- [ ] `web/app.js` line 514: remove `<p class="ws-meta">${esc(org.eventId)}</p>` from workspace header
- [ ] `web/app.js` line 578: remove `factRow("Event ID", fmtId(event.id))` from Content tab
- [ ] `web/app.js` decommission modal (~1339-1350): change confirmation from typing event ID → typing event title
- [ ] Keep event ID in RSVP share URL (functional path parameter, not a label)
- [ ] `web/style.css`: remove `.ws-meta` if unused after removal
- [ ] Verify: e2e tests that reference `.ws-meta` or event ID display — update/remove assertions

## C. Consolidate Content + Bulletin + Media → one "Board" tab
- [ ] Merge three tabs into one `"Board"` tab in organizer workspace
- [ ] Each board post supports: text body, optional type label, optional file attachment, comments
- [ ] Remove "About this event" card (metadata redundant with header/create form)
- [ ] Remove separate Content, Bulletin, Media tab render functions — single `wsBoard()`
- [ ] Attendee event page: same unified board (read-only file links, comment form)
- [ ] Backend: no schema change needed (content_blocks, bulletins+comments, media_assets tables stay; new unified list endpoint serves them interleaved by time)
- [ ] New API: `GET /api/events/{id}/board` returns interleaved posts (content blocks, bulletins, media) sorted by created_at
- [ ] Remove dead per-tab API routes if no other callers exist (keep underlying service methods)
- [ ] `web/style.css`: remove dead tab-specific CSS, add unified `.board-post` styles
- [ ] Verify: unit + e2e green, ruff clean
