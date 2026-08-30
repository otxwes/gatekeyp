# GateKeyp Design System

*`docs/design_system.md` — the source of truth for the visual & interaction language. v1 — Monochrome Edition (Phase 3.5, 2026-08). v0 shipped the warm/vermilion palette; v1 moves the UI to pure paper & ink and adds the motif set.*

## 1. Purpose

This document fixes the design language that `web/style.css` implements and that the Phase 3.6 invite
cards and later phases must follow. It is the covenant between *intent* and *code*: if a value or
pattern isn't here, don't invent it in CSS — add it here first, then wire the token.

- **Applies to:** the web UI (`web/style.css`, `web/app.js`), Phase 3.6 invite cards
  (`web/invite_card.js`), and every future surface.
- **Non-goals:** not a component library API reference, not a marketing brand kit.

## 2. Principles

1. **Are.na-minimal, not SaaS-generic.** Monochrome paper & ink, generous air, hairline
   borders. If a screen "feels generated," it is wrong — see §8.
2. **One ink, used as a verb.** Black (`--accent`) is the single accent — primary buttons,
   active nav/tab, the key moment. It never decorates; in dark it inverts to white. Texture
   (stamps, hatches — §12) does the work color used to do.
3. **Text is the hero; type does the work.** Three faces, each with a job: serif display for
   identity & invitation, system sans for UI & reading, mono for keys & data. Nothing else.
4. **Privacy-lean by construction.** No webfonts, no trackers, no remote assets. The UI is as
   light as the product.
5. **Motion is feedback, not decoration.** Short, purposeful, reducible.
6. **Accessibility is a design constraint, not a QA step.** Contrast, focus, targets, reduced
   motion are baked into tokens.

## 3. Type system

### 3.1 Faces (system stacks only — no webfonts)

| Face | Stack | Job |
|---|---|---|
| **Serif display** | Iowan Old Style, Palatino Linotype, Palatino, Georgia, Times New Roman, serif | Titles, wordmark, keynote moments |
| **Sans UI** | -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif | Chrome, running text, labels |
| **Mono data** | ui-monospace, SF Mono, SFMono-Regular, Menlo, Consolas, Liberation Mono, monospace | Keys, IDs, codes, timestamps, facts |

### 3.2 Scale (always tokenize; never free-type a size)

| Step | Token | px | Primary use |
|---|---|---|---|
| xs | `--text-xs` | 12 | metadata, badges, timestamps, micro-labels |
| sm | `--text-sm` | 14 | captions, hints, nav, fact/toast/modal body |
| base | `--text-base` | 16 | body & running text (a11y floor) |
| md | `--text-md` | 18 | ledes, sub-heads, principle headings |
| lg | `--text-lg` | 22 | card & modal titles |
| xl | `--text-xl` | 28 | *(reserved — panel titles)* |
| 2xl | `--text-2xl` | 36 | view/page titles (fluid clamp) |
| 3xl | `--text-3xl` | 48 | *(reserved — keynote display)* |

Display titles (`view-title`, `ws-title`, `ep-title`) are **fluid** (`clamp()`), sitting
between the fixed steps; everything else picks a step.

### 3.3 Leading & measure

- Display leading: `--leading-display: 1.08` — large serif titles.
- Heading leading: `--leading-tight: 1.2`.
- Body leading: `--leading-normal: 1.6`.
- Body measure: `--measure: 62ch` — never longer. Ledes/intros: `--measure-display: 56ch`.
  Centered micro-copy: `--measure-narrow: 42ch`.

### 3.4 Rules

- Uppercase + wide tracking (`0.12em`) is reserved for **eyebrows** and **badges** — the label
  voice, never body text.
- Negative tracking on display serif only (`-0.01em` wordmark, `-0.015em` view titles,
  `-0.02em` hero).
- Mono for any value the user may copy or compare (keys, IDs, facts) — readability echo of
  "this is data."
- Never justify text; no hyphenation.

## 4. Color

### 4.1 Tokens (light / dark)

Full definitions live in `web/style.css` §1; roles:

| Token | Light | Dark | Role |
|---|---|---|---|
| `--paper` / `--paper-deep` | `#ffffff` / `#f6f6f6` | `#0b0b0b` / `#080808` | page ground / wells & footer |
| `--surface` / `--surface-2` | `#ffffff` / `#f2f2f2` | `#131313` / `#1a1a1a` | cards / inset wells |
| `--ink` / `--ink-soft` / `--ink-faint` | `#111111` / `#4d4d4d` / `#6b6b6b` | `#f5f5f5` / `#c0c0c0` / `#9a9a9a` | text hierarchy |
| `--line` / `--line-strong` | `#e2e2e2` / `#c9c9c9` | `#2a2a2a` / `#404040` | hairline borders |
| `--accent` (+ deep / strong / soft) | `#111111` / `#000000` / `#333333` / ink 8% | `#f5f5f5` / `#ffffff` / `#d9d9d9` / white 10% | action, live state, key moment — ink |
| `--ok` / `--warn` / `--bad` (+ soft) | `#111111` / `#4d4d4d` / `#111111` (+ `#ececec` / `#f4f4f4` / `#ececec`) | `#f5f5f5` / `#c0c0c0` / `#f5f5f5` (+ `#1c1c1c` / `#141414` / `#1c1c1c`) | semantic status — grayscale; meaning via motif §12 + glyphs, never hue |
| `--ok-deep` / `--warn-deep` / `--bad-deep` | `#111111` / `#4d4d4d` / `#111111` | `#f5f5f5` / `#c0c0c0` / `#f5f5f5` | chip/badge ink on soft washes — AA in both themes (item 3) |
| `--accent-contrast` / `--bad-contrast` | `#ffffff` / `#ffffff` | `#0b0b0b` / `#0b0b0b` | ink on filled accent/bad control surfaces (item 3) |
| `--hatch-soft` / `--hatch-fill` / `--hatch-strong` | derived from `--line` / `--surface` (theme-aware) | same, auto | motif fills — texture language (§12) |
| `--dot` | rgba black 4.5% | rgba white 5% | paper ground dot grid ("tooth") |

### 4.2 Rules

- Accent is ink, the single **reserved** color: primary buttons, active nav/tab, links, key
  moments. Sparing by design; the brand mark is the sole persistent accent element.
- Hierarchy comes from the ink steps (`ink → ink-soft → ink-faint`), not from weight games.
- Status is **monochrome + motif**: never hue alone. Badges, banners, and toasts pair ink with
  shape/texture (§12) and glyphs (`⚠` / `✓`), so meaning survives color-blind viewers,
  forced-colors overrides, and print.
- Both themes hold WCAG AA for body text (§10).

## 5. Spacing & layout grid

### 5.1 Rhythm
- Base unit **4px**. Scale: `--space-1` 4 · 8 · 12 · 16 · 24 · 32 · 48 · 72.
- Use a step, never an ad-hoc px. Card inset `--space-5` (24), section y-gaps `--grid-gap`
  (24), micro-gaps `--space-2/3` (8/12). Vertical rhythm doubles around section boundaries.

### 5.2 Grid
- Container: `--container: 1080px` (single `.stage-inner`); text is narrowed further by measure.
- Desk (`.ws-main`) and door (`.ep-main`) are single-column stacks — no side rails — gapped
  with the shared `--grid-gap` rhythm (same as `.split-cards`).
- Breakpoints: **640** (stack forms, full-width buttons) · **420** (tighten card padding).

## 6. Elevation & shape

- **Radii:** `--radius-s` 6 (fields, chips) · `--radius-m` 10 (cards, tiles, banners,
  keycodes) · `--radius-l` 16 (modals). Pills (999px) reserved for badges.
- **Shadows:** `--shadow-1` resting (cards, items), `--shadow-2` floating (modal, toast,
  popover). Never stack shadows; avoid shadows under hairlines.
- **Borders:** hairline 1px — `--line` resting, `--line-strong` interactive/emphasized.
- **Focus:** `--focus-ring` (accent-soft 3px) for fields + `:focus-visible` 2px accent
  outline around. Never remove focus styles.

## 7. Motion language

- **Philosophy:** motion is *feedback* (state change) or *wayfinding* (a surface entered),
  never decoration. Everything ≤ 400ms and reducible (global kill switch already in
  `web/style.css` §17 via `prefers-reduced-motion`).
- **Durations:** `--dur-micro` 120 hover/press · `--dur-fast` 150 small state ·
  `--dur-std` 180 toast/modal · `--dur-view` 250 view/route entrance ·
  `--dur-slow` 400 large/choreographed.
- **Easings:** `--ease-out` (decelerate) for entrances/feedback; `--ease-in-out` for
  theme/color cross-fades. No linear for subjective motion; no bounce/spring.
- **Vocabulary:** `view-in` (fade + 6px rise) route change; `modal-in` (fade + 10px rise +
  0.98 scale) overlays; `toast-in/out` (fade + 8px); button press = 1px translateY; hover =
  color/border change only.
- **Wired (Phase 3.5 item 4, 2026-08):** every rule consumes the tokens — `view-in`, tabs and
  nav links via `--dur-view`; modal & toast entrances via `--dur-std`; buttons, fields, badges,
  items, bulletin, toast-out & fade-in via `--dur-fast`; button press via `--dur-micro`; theme
  cross-fade via `--dur-view` × `--ease-in-out`. The §17 `prefers-reduced-motion` switch is the
  global off switch. No hardcoded durations/easings remain in the sheet.

## 8. No generic generated-look (the decline list)

Following the Phase-3.5 UI research (`docs/research_notes/07_ui_libraries.md`), we
**borrow techniques, not looks**.

**Decline** (reads as "generated SaaS"):
- Glassmorphism / frosted panels as decoration — the topbar blur is the sole functional
  scrim, and it's the exception.
- Gradient text, aurora/mesh backgrounds, animated gradient blobs.
- Neon/laser/spotlight hover borders, glow shadows, distorted hover transforms, rainbow
  dot-cursor effects.
- Emoji-as-icon patterns; marquee/testimonial carousels.
- Rounded-2xl blobs everywhere; "hero with orbiting blobs" layouts.

**Borrow** (technique-level, adapted to the quiet voice):
- 44px touch-target floor on major controls (dense `btn-sm` stays ≥ 32px in inline rows).
- Staggered entrances = short CSS animation delays on lists, clipped to ≤ 2 steps.
- The `:focus-visible` ring pattern; skeleton over spinner for loading.

**Smoke test:** print the screen. If the first reaction is "this came from a template / an
AI landing page," cut the decoration and return to §2.

## 9. Component inventory & states

All Phase-3 components exist; Phase 3.5's unification pass makes each *identical in both
themes* and resolves any drift. Canonical states:

| Component | Classes | States to keep identical across themes |
|---|---|---|
| Buttons | `.btn` (+`-primary/-secondary/-ghost/-danger`, `-sm`, `-block`) | hover bg/border, `:active` 1px, `:disabled` 0.55 opacity |
| Cards | `.card`, `.form-card` | resting `shadow-1`, `--line` hairline |
| Badges / tags | `.badge` (+`-active/-revoked/-warn/-neutral/-ghost`), `.tag` | motif states: active = solid ink fill, warn = dashed keyline + wash, revoked = hatched + double keyline (§12), neutral/ghost = quiet chips |
| Items / key rows | `.item`, `.key-detail-row` | hover `border-color` + `shadow-1` |
| Toasts | `.toast` (+`-ok/-error`) | `--line-strong` + semantic left bar, in/out anim |
| Modals | `.modal-backdrop`, `.modal` | backdrop dim + blur, `shadow-2`, `modal-in` |
| Empty / loading / error | `.empty`(+`-title/-sub`), error toasts | dashed `--line-strong`, `--hatch-fill` "ticket stub" (§12), `measure-narrow` |
| Focus / disabled | `:focus-visible` ring, `[disabled]` | consistent; focus never removed |

## 10. Accessibility & responsive baseline

- **Contrast:** WCAG AA in both themes; body ink is AAA. Spot checks (Phase 3.5 monochrome,
  2026-08): light ink `#111111` on white ≈ **18.9:1**; light soft `#4d4d4d` ≈ **8.5:1**;
  light faint `#6b6b6b` ≈ **5.3:1** (on `--surface-2` `#f2f2f2` ≈ **4.8:1**); dark ink
  `#f5f5f5` on `#0b0b0b` ≈ **18.0:1**; dark soft `#c0c0c0` ≈ **10.8:1**; dark faint `#9a9a9a`
  ≈ **7.0:1** (on `#1a1a1a` ≈ **6.2:1**). Chips/badges: light `#111111`/`#4d4d4d` on
  `#ececec`/`#f4f4f4` ≈ 10–14:1; dark `#f5f5f5`/`#c0c0c0` on `#1c1c1c`/`#141414` ≈ 8–10:1
  (worst-case `--surface-2`). Filled buttons: `#111111` on white ≈ 18.9:1 and `#f5f5f5` on
  `#0b0b0b` ≈ 18.0:1. Full audit lives in `docs/qa_matrix.md`; re-check when values drift.
- **Targets:** ≥ 44px for primary controls (icon-btn 44×44, tabs ≥ 40px tall); dense inline
  rows may use `btn-sm` with gaps so effective touch zones stay usable.
- **Non-color signals:** because status is grayscale, meaning is double-coded — badges use
  motif (§12) and form notes prefix `⚠` / `✓` glyphs. Verify new status UI carries a
  non-color cue before shipping.
- **Keyboard:** full tab order, skip link, `Escape` closes modals, `aria-selected` on tabs,
  live-region announcements for toasts.
- **Reduced motion:** global §17 switch; anything that removes meaning (e.g., theme cross-fade)
  stays ≤ 250ms.
- **QA matrix** (Phase 3.5 item 6): light × dark × mobile/desktop × owner/attendee — see
  `docs/qa_matrix.md`.

## 11. Stack & dependencies policy (frontend)

- **Decision (2026-08): stay vanilla JS + hand-rolled tokens; do NOT adopt React, Tailwind, or
  Motion.** Rationale recorded in `docs/research_notes/07_ui_libraries.md` (its "Guidance vs.
  Phase 3.5 'no generic generated-look'" section + TL;DR); in
  short: zero-build static serving to Co-op Cloud is a deliberate deployment feature, the SPA is
  a thin view over a JSON API, and the hard risk lives server side (Python). A runtime/bundler
  on the one minimal-surface part would add supply chain + payload for no product-risk reduction.
- Any framework adoption will be **incremental** (a second entry for one screen), never big-bang.
- **Review triggers** (revisit if *two* appear, or *one* is a must-have):
  1. Two live connected surfaces sharing browser state (e.g., Phase 4 map + Phase 6 board).
  2. A genuinely must-have React-only widget.
  3. A second front-end dev fluent in React who owns the port.
  4. Animation needs that exceed CSS + Web Animations API (FLIP / orchestrated layout).
- **Already portable:** tokens are plain CSS vars (a Tailwind `@theme` merge maps 1:1); motion
  language is expressible via CSS + WAAPI; `app.js`'s router/`$`/`$$`/`esc()` patterns make a
  future port mechanical.

## 12. Motif set (Phase 3.5 item 5)

With the palette reduced to pure ink, **texture is the second channel**: shape and pattern
carry status and emphasis that hue used to carry. All motif fills are theme-aware (built from
`--line` / `--surface` tokens at use time — they re-derive automatically in dark).

| Motif | Definition | Used for |
|---|---|---|
| **Hatch, soft** `--hatch-soft` | 45° hairline, 10px period | revoked badges, decommission modal (`voided` composite) |
| **Hatch, fill** `--hatch-fill` | 45° `surface`/`surface-2` weave | empty states ("ticket stub"), master banner ground |
| **Hatch, strong** `--hatch-strong` | −45° `line-strong`, 5px period | reserved for the loudest voided moments |
| **Stamp** | dashed / double keylines (`border-style`) | warn badges (dashed), revoked + decommission (double) |
| **Dot tooth** `--dot` | 1px grid on the page ground | the paper's texture (body background) |

Rules:

- Texture is meaningful, never decorative: every hatch/stamp instance names a state
  (well, voided, notice, quiet). If a surface's pattern has no job, remove it.
- Status must never rely on pattern **or** ink alone — pair motif with glyphs/words
  (`⚠`/`✓`, "Revoked", "Active") so meaning survives monochrome print and forced-colors.
- The `.hatch-*` / `.voided` classes are the primitives the Phase 3.6 invite
  cards build on — reuse the tokens, don't invent new textures.
- The paper dot grid is capped at ~5% alpha in both themes; it is a tooth, not a pattern.

## 13. Change management

- Tokens live in `web/style.css` §1; this doc is the **intent layer**. A value changes in CSS
  *and* the intent is noted here.
- New visual pattern → add to §9 inventory first, then implement.
- New color → extend §4.1 with a role + soft-wash pair, then tokenize.
- Drift between this doc and the CSS is a bug — fix the closer source, don't hand-wave.

*Sections 3–8 mirror the tokens already defined in `web/style.css` §1; keep the two in sync on every tokenization change.*
