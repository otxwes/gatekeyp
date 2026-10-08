# Plan — Card-first key UX (no text key display/copy)

Scope approved by user: remove saving the raw key as text everywhere EXCEPT the
lite (flyer) flow, whose organizer-key text + LXMF mesh transport stays as-is.
Paste of `gkp:`/`gkporg:` keylines at door / organize entry stays as an
unadvertised escape hatch (input side, not a save surface).

## Changes
- [ ] `web/app.js openKeyModal` — no key text, no Copy; card button primary.
- [ ] Caller titles → "make the card" wording (create + mint).
- [ ] Workspace banner — remove "Copy organizer key".
- [ ] `keyRowHTML` + binding — remove per-row "Card" action and `openKeyCardModal`.
- [ ] RSVP result — remove key text + Copy; "Make an invite card" primary; "Open the event now" unchanged.
- [ ] Sidebar CSS classes `kc-value` etc. left in place (used by RSVP share link).
- [ ] tests/e2e/pages.py — `ApiKeyGrabber` (network capture) replaces `.kc-value`
      reads; `download_card_for_key` → `mint_key_and_card`; mint closes via
      Cancel; rsvp wait + rsvp_key reworked.
- [ ] README/docs wording sweep where text-key halves are described.
- [ ] Verify: ruff/format, unit pytest, full e2e suite (+ new assertion that no
      `keycode kc-value` appears in mint/RSVP result DOM).
