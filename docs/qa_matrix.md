# GateKeyp QA Matrix — Phase 3.5 (Monochrome Edition)

*`docs/qa_matrix.md` — Phase 3.5 item 6. Run before shipping 3.5 and re-run on any token drift.
Companion to `docs/design_system.md` (§10) and the tokens in `web/style.css` §1.*

Status key: ✅ verified (computed/code-audited) · 👁 manual visual pass (needs a human browser
look; flag anything that reads as broken or "generated").

> **2026-09-08:** the UI is now a **single dark theme** — the light palette and the topbar
> toggle were removed (see `docs/design_system.md` §4.1). The light-theme rows below are the
> historical audit from the two-theme era; §4's matrix predates the consolidation.

## 1. Contrast audit (WCAG 2.1, computed 2026-08-30)

All pairs below are the **worst case** in which each token is used. Body text hits AAA;
secondary/faint text and chips clear AA (≥ 4.5:1) with margin.

### Light theme (ground `#ffffff` / `--surface-2` `#f2f2f2`)

| Pair | Ratio | Verdict |
|---|---|---|
| ink `#111111` on white `#ffffff` | 18.88:1 | ✅ AAA |
| ink-soft `#4d4d4d` on white | 8.45:1 | ✅ AAA |
| ink-faint `#6b6b6b` on white | 5.33:1 | ✅ AA |
| ink-faint `#6b6b6b` on `#f2f2f2` | 4.76:1 | ✅ AA (worst case) |
| ink-soft `#4d4d4d` on chip `#f4f4f4` (warn badge) | ≈ 8:1 | ✅ AA |
| ink `#111111` on chip `#ececec` (ok/bad badge, error toast) | ≈ 14:1 | ✅ AAA |
| white `#ffffff` on filled ink `#111111` (primary btn, active badge) | 18.88:1 | ✅ AAA |

### Dark theme (ground `#0b0b0b` / `--surface-2` `#1a1a1a`)

| Pair | Ratio | Verdict |
|---|---|---|
| ink `#f5f5f5` on `#0b0b0b` | 18.05:1 | ✅ AAA |
| ink-soft `#c0c0c0` on `#0b0b0b` | 10.82:1 | ✅ AAA |
| ink-faint `#9a9a9a` on `#0b0b0b` | 6.99:1 | ✅ AA |
| ink-faint `#9a9a9a` on `#1a1a1a` | 6.19:1 | ✅ AA (worst case) |
| ink-soft `#c0c0c0` on chip `#141414` (warn badge) | ≈ 10:1 | ✅ AA |
| ink `#f5f5f5` on chip `#1c1c1c` (ok/bad badge, error toast) | ≈ 8:1 | ✅ AA |
| near-black `#0b0b0b` on filled ink `#f5f5f5` (primary btn, active badge) | 18.05:1 | ✅ AAA |

**Rule:** any future token change must keep these worst-case pairs ≥ 4.5:1. Hatched/bordered
badges intentionally pair `--bad-deep`/`--warn-deep` ink with lighter washes, so pattern is a
bonus, not the sole carrier of meaning.

## 2. Non-color signals (mandatory now that status is grayscale)

| State | Motif (shape/pattern) | Glyph / word |
|---|---|---|
| Active | solid ink fill (badge-active) | "Active" label |
| Warn | dashed keyline + wash (badge-warn, master "Master" badge) | label + underlined key emphasis |
| Revoked / destructive | hatched + double keyline (badge-revoked, danger zone) | "Revoked" label, "⚠" form notes |
| Empty / quiet | hatched "ticket stub" fill + dashed keyline (`.empty`) | title + sub copy |
| Ok / error toasts | shaded error body + left bar; ok left bar only | `✓` / `✕` icon + text |
| Form notes | `.is-error` (bold ink) / `.is-ok` | `⚠` / `✓` prefix (app.js `note()`) |

✅ `web/style.css` §19 + `web/app.js` `note()` implement the above. Any new status UI must add
a row here before shipping.

## 3. Target-size audit (WCAG 2.5.8 min 24px; project floor 44px for primary)

| Control | Size | Verdict |
|---|---|---|
| `.btn` (primary/secondary) | ≈ 45px tall, full-width on mobile | ✅ |
| `.tab` (workspace tabs) | ≥ 40px tall × generous width | ✅ dense-inline exception, spaced |
| `.btn-sm` / inline rows (`b-toggle`, `c-del`, copy) | ≥ 32px with ≥ 8px gaps | ✅ inline exception per §10 |
| `.badge` | informational, non-interactive | n/a |
| `.nav-link` | ≥ 44px effective | ✅ |

## 4. Theme × role × viewport matrix

Cells: ✅ code-audited this pass · 👁 needs a human visual pass (light + dark).

| | Light · desktop | Light · mobile | Dark · desktop | Dark · mobile |
|---|---|---|---|---|
| **Owner — entry** (create / open forms, notes, buttons) | ✅ | ✅ | ✅ | ✅ |
| **Owner — workspace tabs** (four tabs, header actions) | ✅ | ✅ | ✅ | ✅ |
| **Owner — master-key modal + banner** (keycode, stamp banner) | ✅ | ✅ | ✅ | ✅ |
| **Owner — empty states, badges, toasts** | ✅ | ✅ | ✅ | ✅ |
| **Owner — decommission modal + verify prompt** | ✅ | ✅ | ✅ | ✅ |
| **Attendee — door** (unlock form, key hint) | ✅ | ✅ | ✅ | ✅ |
| **Attendee — event page** (bulletins, media) | ✅ | ✅ | ✅ | ✅ |
| **Both — toasts & form notes** (`✓`/`⚠` glyphs) | ✅ | ✅ | ✅ | ✅ |
| **Both — print** (B&W-only output) | ✅ | — | n/a | — |
| **Both — forced-colors / high-contrast OS** | 👁 | 👁 | 👁 | 👁 |
| **Both — reduced motion** (`prefers-reduced-motion`) | ✅ (global §17) | ✅ | ✅ | ✅ |

## 5. Keyboard & focus

- ✅ Full tab order; skip link; `Escape` closes modals; `aria-selected` on tabs; `role="status"`
  `aria-live` on form notes and the toast region.
- ✅ `:focus-visible` 2px accent outline + `--focus-ring` on fields, never removed.
- 👁 Screen-reader pass (VoiceOver / NVDA) on the door and workspace — recommend a human run.

## 6. Regression sweep

- ✅ `web/style.css` holds **no** warm/vermilion remnants (`#faf8f4`, `#c7421e`, `#ff5c37`,
  `#ff8a63`, warm semantic hexes) — verified by grep; all token consumers reference the new
  grayscale ramp.
- ✅ `web/index.html` favicon is now ink `#111111`; hero + footer carry the `.ornament`.
- ✅ Server test suite green (API + web mount) after the pass.
- 👁 Final visual pass of hatches/ornament legibility on a real display (hatch period vs.
  font-size), and invite-card reuse in Phase 3.6 (design-system §12).

## 7. Running the matrix

1. `python3 -m pytest -q` (Apple Silicon: `arch -x86_64 python -m pytest -q`).
2. Serve: `python3 -m src.api.server` (or `uv run ...`) and open `/`.
3. Step every view at 1280, 768, and 390 px widths (single dark theme — no toggle).
4. Check `prefers-reduced-motion` and forced-colors in DevTools Rendering.

*Last run: 2026-08-30 (computed + code audit). Human visual pass outstanding on cells marked 👁.*
