# Website

A Next.js 15 application that reads markdown content from `/documents/` and generates a static site for GitHub Pages.

All development happens in the `/website/` directory.

## Static Site

The site is a static export — no server at runtime. Every page is pre-rendered at build time. This constrains the architecture: no API routes, no server-side rendering, no dynamic image optimization.

The build outputs static HTML to `out/`, deployed to GitHub Pages at a subpath (`/augmented-coding-patterns/`). Trailing slashes are required for GitHub Pages compatibility.

## Key Pages

- Home (`/`) — three category cards, a search bar, and an interactive relationship graph
- Category list (`/patterns/`, `/anti-patterns/`, `/obstacles/`) — all documents in a category
- Document detail (`/{category}/{slug}/`) — rendered markdown with related items sidebar
- Pattern catalog (`/pattern-catalog/`) — table view of all documents with summaries
- Interactive map (`/talk/`) — canvas-based talk visualization
- Contributors (`/contributors/`) — author listing with contribution stats

## Category Configuration

All category-specific behavior (labels, icons, descriptions, CSS classes) is centralized in `app/lib/category-config.ts`. Nothing is hardcoded per-category elsewhere. Adding a new category means adding one config entry.

## Features

Search — client-side full-text search across all documents, grouped by category in a dropdown

Relationship graph — force-directed visualization on the home page using `react-force-graph-2d`, nodes color-coded by category, edges by relationship type, clickable to navigate

Theme — light/dark mode toggle, persisted in localStorage, applied before first paint to avoid flash

## Testing

- Unit tests (Jest) — components, markdown processing, relationship parsing
- E2E smoke tests (Playwright, Chromium only) — critical navigation paths
- Relationship validation (`npm run validate`) — ensures all graph references point to existing documents

## Commands

From `/website/`:

```
npm run dev        Development server (Turbopack)
npm test           Unit tests
npm run test:e2e   E2E smoke tests
npm run lint       ESLint (must be 0 errors, 0 warnings)
npm run validate   Validate relationship graph
npm run build      Static export to out/
```
