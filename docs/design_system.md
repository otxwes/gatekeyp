# GateKeyp Design System

*`docs/design_system.md` — the source of truth for the visual & interaction language. v0 (Phase 3.5, 2026-08).*

## 1. Purpose

This document fixes the design language that `web/style.css` implements and that the Phase 3.6 invite
cards and later phases must follow. It is the covenant between *intent* and *code*: if a value or
pattern isn't here, don't invent it in CSS — add it here first, then wire the token.

- **Applies to:** the web UI (`web/style.css`, `web/app.js`), Phase 3.6 invite cards
  (`web/invite_card.js`), and every future surface.
- **Non-goals:** not a component library API reference, not a marketing brand kit.

## 2. Principles

1. **Are.na-minimal, not SaaS-generic.** Quiet editorial warmth: warm paper, near-black ink,
   generous air, hairline borders. If a screen "feels generated," it is wrong — see §9.
2. **One accent, used as a verb.** Vermilion (`--accent`) is for *action and live state* —
   primary buttons, links, active nav/tab, the key moment. It never decorates.
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
| 3xl | `--text-3xl` | 48 | hero display (fluid clamp) |

Display titles (`hero-title`, `view-title`, `ws-title`, `ep-title`) are **fluid** (`clamp()`), sitting
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
| `--paper` / `--paper-deep` | `#faf8f4` / `#f3efe7` | `#161412` / `#12110e` | page ground / wells & footer |
| `--surface` / `--surface-2` | `#ffffff` / `#f5f1ea` | `#201d19` / `#27231f` | cards / inset wells |
| `--ink` / `--ink-soft` / `--ink-faint` | `#21201c` / `#6d675c` / `#9b9488` | `#f0ece2` / `#b9b1a1` / `#827a6b` | text hierarchy |
| `--line` / `--line-strong` | `#e6e0d4` / `#d8d0c2` | `#332e28` / `#423c34` | hairline borders |
| `--accent` (+ deep / strong / soft) | `#c7421e` family | `#ff5c37` family | action, live state, key moment |
| `--ok` / `--warn` / `--bad` (+ soft) | green / amber / red | brightened | semantic status |

### 4.2 Rules

- Accent is a **reserved color**: primary buttons, active nav/tab, links, highlights. Sparing by
  design; the brand mark is the sole persistent accent element.
- Hierarchy comes from the ink steps (`ink → ink-soft → ink-faint`), not from weight games.
- Status colors always ride on a **soft wash** (`--ok-soft` etc.) for chips/badges — never raw
  status color on raw surface.
- Both themes hold WCAG AA for body text (§10).

## 5. Spacing & layout grid

### 5.1 Rhythm
- Base unit **4px**. Scale: `--space-1` 4 · 8 · 12 · 16 · 24 · 32 · 48 · 72.
- Use a step, never an ad-hoc px. Card inset `--space-5` (24), section y-gaps `--grid-gap`
  (24), micro-gaps `--space-2/3` (8/12). Vertical rhythm doubles around section boundaries.

### 5.2 Grid & rails
- Container: `--container: 1080px` (single `.stage-inner`); text is narrowed further by measure.
- Desk (`.ws-body`) and door (`.ep-grid`) are two-column: main `minmax(0, 1fr)` +
  `--rail: 340px` sidebar — the same token, both surfaces. Rails collapse to one column < 900px.
- Card stacks, `.split-cards`, and `.principles` all use the shared `--grid-gap` rhythm.
- Breakpoints: **900** (collapse rails) · **640** (stack forms, full-width buttons) ·
  **420** (tighten card padding).

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
- Tokens are declared now; the Phase 3.5 motion pass wires them into the rules above.

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
| Badges / tags | `.badge` (+`-active/-revoked/-warn/-neutral/-ghost`), `.tag` | soft-wash bg + semantic ink, pill |
| Items / key rows | `.item`, `.key-detail-row` | hover `border-color` + `shadow-1` |
| Toasts | `.toast` (+`-ok/-error`) | `--line-strong` + semantic left bar, in/out anim |
| Modals | `.modal-backdrop`, `.modal` | backdrop dim + blur, `shadow-2`, `modal-in` |
| Empty / loading / error | `.empty`(+`-title/-sub`), error toasts | dashed `--line-strong`, `--surface-2`, `measure-narrow` |
| Focus / disabled | `:focus-visible` ring, `[disabled]` | consistent; focus never removed |

## 10. Accessibility & responsive baseline

- **Contrast:** WCAG AA in both themes. Spot checks: accent `#c7421e` on white ≈ **4.9:1**
  (AA normal text); verify `ink-soft`/`ink-faint` pairs on paper in light and on the brightened
  dark palette (both themes already pass 4.5+ for body; re-check when values drift).
- **Targets:** ≥ 44px for primary controls; dense inline rows may use `btn-sm` with gaps so
  effective touch zones stay usable.
- **Keyboard:** full tab order, skip link, `Escape` closes modals, `aria-selected` on tabs,
  live-region announcements for toasts.
- **Reduced motion:** global §17 switch; anything that removes meaning (e.g., theme cross-fade)
  stays ≤ 250ms.
- **QA matrix** (Phase 3.5 item 6): light × dark × mobile/desktop × owner/attendee, run before
  shipping 3.5.

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

## 12. Change management

- Tokens live in `web/style.css` §1; this doc is the **intent layer**. A value changes in CSS
  *and* the intent is noted here.
- New visual pattern → add to §9 inventory first, then implement.
- New color → extend §4.1 with a role + soft-wash pair, then tokenize.
- Drift between this doc and the CSS is a bug — fix the closer source, don't hand-wave.

*Sections 3–8 mirror the tokens already defined in `web/style.css` §1; keep the two in sync on every tokenization change.*
