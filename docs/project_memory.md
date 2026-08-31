# Project Memory

This document serves as the durable, self-improving memory for the gatekeyp project. It captures lessons learned, tooling solutions, process improvements, and coding practices discovered during development. **This is a living document** — update it whenever you encounter a worthwhile lesson.

## How to Use This Document

- **Before starting a task**: Skim this document for relevant lessons that may apply.
- **During a task**: If you hit an error or discover a better approach, note it here.
- **After a task**: Review what you learned and add any new lessons.
- **When updating**: Add entries to the appropriate section, keep entries concise and actionable.

---

## 1. Tooling Solutions & Error Fixes

### 1.1 uv (Package Manager)

- **uv sync creates a virtual environment automatically** — no need to manually create one with `python -m venv`.
- **Use `uv run <command>`** to execute tools within the project environment (e.g., `uv run pytest`, `uv run ruff check`).
- **Dependency groups in `pyproject.toml`** keep dev/test/audit dependencies separate from runtime dependencies.
- **`uv.lock` provides reproducible builds** — always commit it to version control.
- **`uv sync` is idempotent** — safe to run repeatedly; it only installs what's missing.

### 1.2 Pre-commit Hooks

- **`pyupio/safety` hook is broken** — the repo at rev `3.2.0` has an invalid `.pre-commit-hooks.yaml` manifest. Use `pip-audit` instead (via `uv run pip-audit` or the `audit` dependency group).
- **`pip-audit` as a pre-commit hook can fail on Apple Silicon** — the pre-commit isolated environment may install x86_64 wheels that are incompatible with arm64. Run `pip-audit` via `uv run pip-audit` instead of as a pre-commit hook.
- **Pre-commit hooks may modify files** (e.g., `ruff format`, `end-of-file-fixer`) — always run `pre-commit run --all-files` before committing, and re-stage files after hooks modify them.
- **When a commit is blocked by pre-commit**, the hooks have already modified files. Re-stage with `git add -A` and retry the commit.
- **`pre-commit install`** installs the git hook that runs on every commit. Run it once after setting up the project.

### 1.3 Ruff (Linter & Formatter)

- **Ruff's `ALL` ruleset is aggressive** — use `per-file-ignores` for test files to suppress rules that don't apply (e.g., `S105`/`S106` for hardcoded passwords in test fixtures, `PT009` for unittest-style assertions).
- **`ruff format` and `ruff check` are separate commands** — run both to ensure code is both formatted and lint-clean.
- **Ruff can auto-fix many issues** with `ruff check --fix` — run this before manually fixing.
- **Common rules to ignore for tests**: `ANN001`, `ANN201`, `ANN202`, `CPY001`, `ERA001`, `PLC0415`, `PT009`, `PT011`-`PT027`, `PTH100`, `PTH120`, `S105`-`S108`, `SLF001`, `TID252`.

### 1.4 Ty (Type Checker)

- **Ty is a fast Python type checker** — use `uv run ty check src/` to type-check the source code.
- **Type narrowing with `isinstance()`** — when a variable can be `None` or a specific type, use `isinstance()` checks to narrow the type before accessing attributes.
- **Ty may flag issues that mypy doesn't** — always run both if available.

### 1.5 Docker

- **Multi-stage builds** keep the final image small — use a builder stage for dependencies and a runtime stage for the application.
- **`uv` works well in Docker** — use `uv sync --frozen` in the builder stage for reproducible installs.
- **Use `--no-cache-dir`** with pip to avoid caching issues in containers.

### 1.6 MCP Servers

- **MCP servers are configured in `.mcp.json`** — each server has a `command`, `args`, and `env` configuration.
- **GitHub MCP server** requires a `GITHUB_PERSONAL_ACCESS_TOKEN` environment variable.
- **Filesystem MCP server** provides file read/write/search capabilities.
- **Fetch MCP server** provides web content fetching.
- **Cline user-level MCP config lives at `~/.cline/data/settings/cline_mcp_settings.json`** (not the legacy `globalStorage/saoudrizwan.claude-dev` path). Format: `{"mcpServers": {"<name>": {"transport": {"type": "stdio", "command", "args", "env"}}}}`. Remote servers use `"type": "streamableHttp"` + `"url"`.
- **`spawn -- ENOENT` means the config literally sets `"command": "--"`** — Cline tried to execute a program named `--`. The real executable had been misplaced in `args`. `command` must be the executable, `args` the arguments.
- **GUI-launched VS Code / Cline have a minimal `PATH`** (Homebrew dirs like `/usr/local/opt/*/bin` and `/usr/local/bin` are missing). Fix: use absolute paths for `command` **and** set `"env": {"PATH": "/usr/local/opt/node/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"}` on the transport.
- **npx still needs `node` on PATH** even when invoked via an absolute node + npx-cli path — npm resolves the package's `#!/usr/bin/env node` bin through PATH. Add the node bin dir to the transport `env.PATH`, and pass `-y` so npx never blocks on an install prompt. Working pattern: `command: "/usr/local/opt/node/bin/node"`, `args: ["/usr/local/opt/node/libexec/lib/node_modules/npm/bin/npx-cli.js", "-y", "<pkg>"]`.
- **Homebrew `node` was installed but never linked** (no `node`/`npm`/`npx` in `/usr/local/bin`); the keg path `/usr/local/opt/node/bin/*` and `npx-cli.js` are stable regardless of symlinks.
- **Semgrep MCP**: the OSS `semgrep` binary's `semgrep mcp` and `semgrep-mcp`'s `semgrep --pro --version` both require the Pro engine — `semgrep login` + `install-semgrep-pro`, or `SEMGREP_APP_TOKEN` set. `uvx semgrep-mcp` additionally shells out to a `semgrep` CLI that must be on PATH. Validate a server by piping an `initialize` JSON-RPC request and grepping `"serverInfo"` from the response.

### 1.7 Sub-Agents

- **Sub-agents are configured in `.agents/workflows.json`** — each workflow defines a prompt template and expected output.
- **Use sub-agents for parallel research** — they can explore different parts of the codebase simultaneously.
- **Sub-agents are most useful for** security audits, dependency audits, and code reviews.

---

## 2. Process Improvements

### 2.1 Development Workflow

- **Always run the full verification suite before committing**: `uv run pytest tests/ -q && uv run ruff check . && uv run ty check src/`.
- **Run `pre-commit run --all-files`** before committing to catch issues early.
- **Commit in logical units** — separate infrastructure changes from feature changes from documentation changes.
- **Use `git add -A` after pre-commit modifies files** — hooks may reformat or fix files, and you need to re-stage them.

### 2.2 Testing

- **Property-based testing with Hypothesis** catches edge cases that example-based tests miss.
- **Test fixtures in `tests/conftest.py`** provide shared setup for all tests.
- **Test helpers in `tests/helpers.py`** provide reusable utilities.
- **Security audit tests** should verify that hardcoded secrets, weak auth, and permissive security are not present.

### 2.3 Documentation

- **Keep documentation in sync with code** — when you change behavior, update the relevant docs.
- **Use the `skills/` directory for reusable instruction sets** — each skill has YAML frontmatter with `name` and `description`.
- **The `skills_manifest.md` tracks all installed skills** — update it when adding or removing skills.

---

## 3. Coding Practices

### 3.1 Python

- **Use modern Python (3.11+)** — take advantage of `match` statements, `Self` type, `TypeVarTuple`, etc.
- **Use type hints everywhere** — Ty and Ruff will enforce this.
- **Prefer `pathlib.Path` over `os.path`** — it's more modern and type-safe.
- **Use `cryptography` for crypto operations** — it's well-maintained and audited.
- **Use `argon2-cffi` for password hashing** — Argon2 is the recommended password hashing algorithm.

### 3.2 Security

- **Never hardcode secrets** — use environment variables (see `.env.example`).
- **Use `secrets` module for cryptographic random values** — not `random`.
- **Validate all inputs** — especially from external sources.
- **Follow the threat model** in `docs/threat_model.md` — it defines the security boundaries.

### 3.3 Testing

- **Write tests before or alongside code** — test-driven development catches bugs early.
- **Use property-based testing for** serialization, crypto operations, and data validation.
- **Test both happy paths and edge cases** — empty inputs, invalid inputs, boundary values.

### 3.4 Browser JavaScript (no Node on this machine)

- **JXA (`osascript -l JavaScript`) is a real JavaScriptCore runtime** — use it for
  syntax checks (`new Function(src)`) and for running pure JS functions against
  Python-computed golden values (`tests/jxa_stego_check.py`). It parses modern
  syntax (BigInt literals, template literals, arrow functions) but **its BigInt
  `%` and `/` are broken** (return garbage) — verify positions with bitwise long
  division instead. `console.log` goes to **stderr**, not stdout.
- **64-bit constants must be BigInt literals in JS**: `0x9e3779b97f4a7c15` is an
  imprecise float64 (loses bits above 2^53), so `BigInt(0x9e3779b97f4a7c15)`
  silently produces a different seed than Python's exact integer — write
  `0x9e3779b97f4a7c15n` and keep the Python mirror's `int` exact. A drift here
  breaks every cross-language test without an error.
- **Classic-script modules need their factory invoked**: `window.X = (function () {...});`
  assigns the function itself; the trailing invocation `})();` is required. The
  JXA parse check caught this after plain review missed it.
- **Keep `new Function(...)` only for parsing**: JXA `eval` of a whole file has
  scope surprises — assemble a temp script (hooked source + assertions) and run
  it as a file instead.

---

## 4. Project-Specific Knowledge

### 4.1 Architecture

- **gatekeyp is a privacy-preserving, federated event-organizing toolkit**.
- **Core components**:
  - `src/core/key_manager.py` — Key system (HMAC-SHA256, Argon2id, rotation, revocation)
  - `src/core/content_manager.py` — Media assets, bulletins, comments (encrypted at rest)
  - `src/core/event_lifecycle.py` — Event creation, access keys, decommissioning
  - `src/api/gateway.py` — Rate-limited API gateway
  - `src/api/server.py` — FastAPI HTTP server + static web UI
  - `src/db/database_handler.py` — SQLite with encryption-at-rest (Fernet/AES-GCM)
- **Key system**: Uses HMAC-SHA256 keyed hashing (per-instance secret) and optional Argon2id for higher-cost verification.
- **Federation**: See `docs/federation_specification.md` for the federation design.
- **Database schema**: See `docs/database_schema.md` for the schema design.
- **Key specification**: See `docs/key_specification.md` for the Key system design.
- **Web UI**: `web/` directory contains the static frontend (HTML, CSS, JS) served by the FastAPI server.

### 4.2 Roadmap

- **Phase 1**: Core Architecture (Key logic, database, secure backend) ✅
- **Phase 2**: Content & Communication (flyers, descriptions, media) ✅
- **Phase 3**: Frontend & UX/UI Design ✅
- **Phase 4**: Map & Navigation (OpenStreetMap, geofencing)
- **Phase 5**: Payment & Ticketing (Monero)

---

## 5. Self-Improvement Log

### 2026-08-02 — Initial Infrastructure Modernization

**What was done:**
- Migrated from `requirements.txt` to `pyproject.toml` with `uv` as the package manager
- Added Docker containerization
- Added MCP server configuration
- Added sub-agent workflows
- Added pre-commit lifecycle hooks
- Added security audit tests and property-based testing
- Added 4 new skills (modern_python, insecure_defaults, property_based_testing, supply_chain_audit)

**Lessons learned:**
1. `pyupio/safety` pre-commit hook is broken — use `pip-audit` instead
2. `pip-audit` as a pre-commit hook can fail on Apple Silicon due to architecture mismatch — run it via `uv run pip-audit` instead
3. Pre-commit hooks modify files — always re-stage after running them
4. Ruff's `ALL` ruleset requires extensive `per-file-ignores` for test files
5. `uv sync` automatically creates a virtual environment — no manual venv creation needed
6. Type narrowing with `isinstance()` is essential for Ty to pass on optional values

**Next steps:**
- Continue building out Phase 1 (Core Architecture)
- Add CI/CD pipeline (GitHub Actions)
- Add more property-based tests for crypto operations
- Consider adding a `docs/decisions.md` for architectural decision records (ADRs)

### 2026-08-02 — Phase 2: Content & Communication Layer

**What was done:**
- Implemented `ContentManager` for media assets (flyers, images, documents) with encryption-at-rest
- Implemented secure communication boards (bulletins with encrypted bodies, threaded comments)
- Implemented `EventLifecycleManager` for end-to-end event orchestration (creation, access keys, decommissioning)
- Added FastAPI HTTP server (`src/api/server.py`) with RESTful endpoints for all features
- Added static web UI (`web/`) — mobile-first, privacy-preserving frontend
- Added `fastapi`, `python-multipart`, and `uvicorn` dependencies
- Expanded test suite from 77 to 123 tests (all passing)

**Lessons learned:**
1. FastAPI's `UploadFile` requires `python-multipart` for form data handling
2. Static file serving in FastAPI is straightforward with `StaticFiles` and `FileResponse`
3. CORS middleware is needed for development when the frontend and API are on different origins
4. Content managers should share the same `DatabaseHandler` and `KeyManager` instances to maintain consistency
5. Event lifecycle management benefits from a dedicated manager class that orchestrates multiple services
6. MIME-type validation and size limits are essential for media upload security

**Next steps:**
- Begin Phase 3: Frontend & UX/UI Design (refine web UI, accessibility, responsive polish)
- Add CI/CD pipeline (GitHub Actions)
- Consider adding a `docs/decisions.md` for architectural decision records (ADRs)

### 2026-08-18 — Phase 3: Frontend & UX/UI Design (Redesign)

**What was done:**
- Repaired `web/index.html` structure (balanced sections, forms, containers; added toast/modal roots).
- Rewrote `web/style.css` as a complete editorial/minimalist design (~1620 lines: design tokens, dark/light themes, responsive breakpoints, reduced-motion, print).
- Implemented `web/app.js` as a hash-routed, dependency-free SPA (~1330 lines):
  - Organizer desk: create / open events; four-tab workspace (Content, Bulletin
    board, Media, Access keys) + header Decommission action; one-time master-key modal.
  - Attendee door: key-based unlock, content/bulletins/media with commenting.
  - Session keys in `sessionStorage`; raw keys shown once; toasts, confirm
    modals, loading/empty states, theme toggle, keyboard + reduced-motion support.

**Lessons learned:**
1. No Node.js runtime and no reliable JS formatter on this machine — validated
   the 1333-line SPA with a purpose-built Python lexer (balanced delimiters,
   strings, comments, and nested template literals verify structurally sound).
2. The terminal corrupts large heredocs — use the editor tool for file writes.
3. The venv's `cryptography` wheel is x86_64 — tests must run under Rosetta:
   `arch -x86_64 python -m pytest -q` (136 pass).
4. Gateway `/api/access` returns `{status, data}` with HTTP 200 even on errors —
   the attendee unlock flow must branch on `status`, not HTTP status.
5. Matching the SPA markup to pre-existing CSS hooks (badges, bulletin tiles,
   toasts, media tiles) meant most component classes were already styled;
   only a small CSS addendum (`.badge-ghost`, standalone `.section-text`,
   flex `.inline-form`) was needed.

**Next steps:**
- Phase 4: Map & Navigation (OpenStreetMap, geofencing) — begin.
- Run the SPA against a live server for a manual end-to-end pass.
- Add CI/CD pipeline (GitHub Actions) including a JS syntax-check job.

### 2026-08-30 — Phase 3.5: UI simplification (de-chrome pass)

**What was done** (uncommitted, on top of the Monochrome Edition work):
- `web/index.html` — replaced the hero with a minimal `.view-head`; removed the
  footer and ornament dividers.
- `web/app.js` — collapsed the six-tab workspace to four (Content, Bulletin board,
  Media, Access keys); folded Overview into Content (About card + fact list); moved
  Decommission into a header button opening a type-the-ID confirm modal; removed the
  workspace "Event facts" sidebar and attendee About/Your-key side panels; dropped
  the `fmtDay` helper and `loadWsFacts`/`wsOverview`/`wsDecommission` functions.
- Removed the helper prose / captions everywhere: the three view-header paragraphs
  (landing / organize / join), the five card `section-sub` captions, the "Open an
  existing event" lead, the decorative empty-state second lines, and the
  master-banner copy (banner now shows the Master badge + Copy button only).
  Media captions, the event description, and metadata were kept.
- `web/style.css` — removed the orphaned chrome: `.hero*` (hero → `.home-actions`),
  `.principles`, `.ornament*`, `.footer`, the `.ws-body`/`.ws-side` and `.ep-grid`/`.ep-side`
  rail grids, `.danger-zone`/`.verify-prompt`, `.section-divider`, and the `--rail`
  token; dropped the 900px rail-collapse breakpoint; renumbered sections 13–17.

**Verified:**
- No Node runtime on this machine — used a delimiter-balance check on `app.js`
  (504 template-literal backticks; braces/parens/brackets all even) plus a live-server
  end-to-end smoke test (create event → content/bulletin/access-key → attendee unlock →
  decommission, with the post-decommission key correctly rejected).
- Served `app.js`/`index.html`/`style.css` are byte-identical to disk and contain none
  of the removed classes/ids.

**Next steps:**
- Manual hard-refresh visual pass (light/dark, mobile) on the new 4-tab layout.
- Commit the Phase 3.5 work (design system, QA matrix, simplification).

### 2026-08-30 — Phase 3.6: Steganographic Invite Keys

**What was done** (uncommitted):
- `web/stego.js` — zero-dependency PNG low-bit codec (`embed`/`extract` +
  payload/QR helpers): manual PNG parse (all five filters, CRC-verified chunks,
  colour types 0/2/3/4/6), zlib via `CompressionStream`/`DecompressionStream`,
  `GKP1` container with CRC32, xorshift64-scrambled LSB ±1 embedding with
  three-channel replication + majority vote + per-channel fallback.
- `tests/stego_ref.py` — stdlib-only byte-for-byte Python mirror + `--write-fixture` /
  `--decode` CLI; `tests/test_stego_invites.py` (21 tests: Hypothesis round-trips,
  golden vectors, five-filter/colour-type coverage, one-channel corruption
  recovery, capacity edges, committed fixture); `tests/fixtures/invite_fixture.png`.
- `tests/jxa_stego_check.py` + `.js` — parses the shipped JS in JavaScriptCore and
  pins its internals (crc32, PRNG stream, positions, payload/QR/container) to
  Python golden values without a Node runtime.
- `web/vendor/qrcode-generator.js` (+ LICENSE) — MIT `kazuhikoarase` QR encoder for
  the survives-re-encode fallback on the card.
- `web/vendor/jsqr.js` (+ `jsqr-LICENSE.txt`) — **Apache-2.0** (not MIT as first
  assumed — LICENSE file satisfies attribution) `cozmo/jsQR` UMD decoder, 256 KB;
  used by the door QR fallback and the JXA QR round-trip pin.
- `web/door_qr.js` — `window.gkpDoorQr.decode(file)`: draws the dropped image to
  a capped (1600 px) offscreen canvas and runs the vendored jsQR on the RGBA
  buffer; `stego.js` `classifyInvite`/`inviteRejectReason` (magic-byte sniffing
  + honest per-kind rejection) mirrored in `stego_ref.py`.
- `web/invite_card.js` — portrait 800×1200 paper-and-ink card renderer + stego
  download; `web/app.js` — "Also make an invite card" in the one-shot key modal,
  per-row "Card" action (re-enters the raw key), `org.meta` event metadata; door
  drop/paste/choose zone with local decode + auto-fill; `web/index.html` +
  `web/style.css` — drop-zone markup and `.key-drop` ticket-stub styling.
- `docs/steganography_invites.md`, threat-model Phase 3.6 status, roadmap
  checkboxes + context.

**Bugs the cross-check caught** (worth remembering):
- `window.gkpStego = (function () {...});` was missing the trailing `())()` — the
  module object was the factory function itself; would have broken every caller.
- `SEED = 0x9e3779b97f4a7c15` (Number) rounds above 2^53, so `BigInt(SEED)` gave a
  different seed than Python's exact int — JS and Python would never agree in a
  real browser. Fixed with a BigInt literal.
- JXA's BigInt `%`/`/` are broken (return garbage); harness uses bitwise long
  division. Also: `osascript` logs to stderr, and JXA `eval` scope differs — run
  assembled scripts as files.

**Verified:**
- `arch -x86_64 python -m pytest -q` → 166 passed; `python -m tests.jxa_stego_check`
  → JXA-OK (now incl. door `classifyInvite`/`inviteRejectReason` pins + a QR
  encoder→jsQR round-trip + a noise-decode-must-null guard); ruff clean on the
  new Python files; all web JS files parse under JavaScriptCore. Fixture
  regenerates deterministically.

**Next steps:**
- Live-server browser E2E (create → generate key → make card → download →
  Python `--decode` → door drop → unlock; plus door drop of a *re-encoded
  JPEG* to exercise the QR fallback and the honest rejection), then commit C
  (resilience batch) and D (custom covers).
- Manual visual pass on the card art and the door drop zone (light/dark, mobile).

### 2026-08-30 — Commit C (door QR resilience) + Commit D (custom covers)

**Commit C — resilience batch** (landed `447b26a`):
- `web/vendor/jsqr.js` (+ Apache-2.0 LICENSE), `web/door_qr.js` local QR decode
  at the door, `classifyInvite`/`inviteRejectReason` honest rejection + share
  guidance; JXA pins for the door helpers + a QR encoder→jsQR round-trip.

**Commit D — custom covers** (this commit):
- `web/invite_card.js` — cover engine: `coverFit` (object-fit:cover crop
  math), `drawPreset` (hatch / keyline / dots / keyhole), `drawCoverBand`,
  `renderCover` (picker swatches), async `loadCoverImage`; `render()` gained a
  `scale` option (live 200×300 preview) and draws the cover band (704×240)
  above the title — title/rule/meta shifted down, QR + bottom rail untouched.
- `web/app.js` — `openCardCoverModal` (preset chips with live swatches +
  "Own image…" upload + live preview); both the one-shot card button and the
  per-row "Card" action route through it (purely client-side; keys never leave
  the tab). Also fixed a pre-existing `$(" #key-card-key")` leading-space
  selector bug in the same function.
- `web/style.css` §18 — cover picker + preview styles (token-driven,
  monochrome, dark-safe).
- `tests/card_ref.py` — oracle mirror (`cover_fit` + canonical preset ids);
  `tests/test_invite_card_cover.py` — golden vectors, Hypothesis
  object-fit:cover properties, JS↔oracle preset-id lock-step; the JXA harness
  now also loads `invite_card.js` and pins `coverFit` vs Python; E2E static
  needle for `coverFit`.
- No tests pin the card geometry, so shifting the title/rule/meta down was
  safe; the stego E2E loop is geometry-agnostic (still green).

**Verified:** `arch -x86_64 python -m pytest -q` green; ruff clean; JXA-OK
(incl. the new `coverFit` pins); door-QR smoke green; card renders with
presets and an uploaded image in the manual browser pass.

**Next steps:**
- Phase 4 — Map & Navigation.
- Optional cover polish: more presets / per-preset density variants; per-event
  cover persistence would need server surface and is deliberately out of scope.

### 2026-08-30 — Session end: Commit D landed, localhost is live for review

**State at session end:**
- Commit D landed as `5c57b4b` ("feat: custom covers for the invite card —
  preset patterns + own-image upload"); 11 files, +581/−35, working tree
  clean, origin/main in sync (pushed).
- Local dev server (`src.api.server`, PID 9180) live on `127.0.0.1:8000`,
  serving `web/` from disk via `StaticFiles` — web/* edits go live per-request
  with no restart; only `src/*` backend changes need a server restart.

**Validation recap (all green at end of session):**
- `arch -x86_64 python -m pytest -q` → **170 passed** (166 + 4 new cover tests).
- ruff check + format clean; pre-commit hook fully green on the commit.
- JXA cross-check (`python -m tests.jxa_stego_check`) → JXA-OK, now incl.
  `coverFit` pins vs the Python oracle.
- COVER-SMOKE-OK via JXA stub-context — 30,575 drawing ops across every
  render path (classic, scaled, 4 presets, none/absent, image, renderCover
  variants, coverFit degenerates).
- All web JS parses under JavaScriptCore (JS-PARSE-OK).

**Small last-minute polish (after the first smoke, before commit):**
- `renderCover` now also frames the "None" swatch (paper ground + keyline), so
  every chip in the cover picker reads consistently.

**Verified live via curl against the running server** (not just the tree):
`invite_card.js` (11 cover-engine markers), `app.js` (10 cover-modal markers),
`stego.js` / `door_qr.js` / `vendor/jsqr.js` all 200, `index.html` wires all
six scripts in order.

**Next session — review + test checklist:**
1. Browser E2E on `http://127.0.0.1:8000`: create → open event → Access keys →
   "Make an invite card" (top button) **and** per-row "Card" action → select
   each preset + an own-image upload (cover-fit) → Download card → Python
   `--decode` → door drop → unlock.
2. Door drop of a *re-encoded JPEG* card to exercise the jsQR fallback +
   honest rejection + share guidance.
3. Manual visual pass on the card art, cover picker, and door drop zone
   (light/dark, mobile).
4. Then Phase 4 — Map & Navigation.

---

### 2026-08-31 — Session end: invite card stripped to a text-free minimalist layout

**What changed:**
- `web/invite_card.js` — the card is now **text-free**: the "PRINTED KEY ·
  INK ON PAPER" stamp band, the event name, the organizer/location line, and
  the platform captions under the QR are all gone. New composition: double
  keyline frame → keyhole ornament (top, centered) → **704×600 hero cover
  band** (at 48,120 → y=120..720; preset pattern or uploaded photo drawn
  cover-fit; "none"/absent keeps dotted paper) → centered 240px uncaptioned
  QR (tray ≈ y=774..1046) → keyhole ornament (bottom, centered, y=1130). No
  overlaps; the cover art is the sole focus.
- Dead code removed: `wrapText`, `fmtEventId`, and the unused constants
  (`INK_SOFT`, `INK_FAINT`, all `FONT_*`). `PAPER_DEEP` stays (QR tray fill).
- `web/app.js` — `inviteCardOpts()` no longer passes organizerId/location;
  `title` survives only to name the download (`<title>-invite.png`).
- `docs/steganography_invites.md` §5 — cover band corrected to a 704×600 hero
  band under the top keyhole (was "704×240 at the top"); added the text-free
  card description (payload lives only in pixels + QR; no organizer,
  location, or caption text printed).

**Validation recap (all green at end of session):**
- `arch -x86_64 python -m pytest -q` → **170 passed**.
- `python -m tests.jxa_stego_check` → JXA-OK (JS↔Python oracle agreement).
- All web JS parses under JavaScriptCore (checked mid-session).
- Visual pass via Playwright on the browser canvas: 3 cover variants
  (paper / keyhole / hatch) — no text artifacts, QR centered, keyholes
  top/bottom only, hero band prominent, QR clears the bottom keyhole.

**Also in this working tree (uncommitted until now):** Cline MCP env notes
added earlier to this file (user-level config path, `spawn -- ENOENT`
diagnosis) — committed together with this entry.

**Next session:**
1. Browser E2E on `http://127.0.0.1:8000` with the new card art: generate →
   card (each preset + image upload) → download → `tests.stego_ref --decode`
   → door drop → unlock; plus a re-encoded JPEG card for the jsQR fallback.
2. Print one card at actual size to sanity-check the hero band on paper.
3. Then Phase 4 — Map & Navigation.
