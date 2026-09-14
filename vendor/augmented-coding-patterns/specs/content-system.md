# Content System

All content lives in `/documents/` organized into three category directories:

```
documents/
├── patterns/          Proven strategies (e.g., active-partner.md)
├── anti-patterns/     Common mistakes (e.g., ai-slop.md)
├── obstacles/         Inherent limitations (e.g., hallucinations.md)
└── relationships.mmd  Connection graph (see relationships.md)
```

## Document Format

Each document is a markdown file with YAML frontmatter and a specific structure.

Filename is kebab-case and becomes the URL slug: `chain-of-small-steps.md` → `/patterns/chain-of-small-steps/`

### Frontmatter

```yaml
---
authors: [author_id]
---
```

`authors` is the only required field. Author IDs reference entries in `website/config/authors.yaml`.

### Title Convention

The first H1 line is the document's title. Category suffixes are included in the file but stripped for display:

```markdown
# Context Rot (Obstacle)        → displayed as "Context Rot"
# AI Slop (Anti-pattern)        → displayed as "AI Slop"
# Active Partner                → displayed as "Active Partner"
```

Patterns don't need a suffix. Anti-patterns and obstacles include theirs for clarity when reading the raw markdown.

An optional emoji can lead the title: `# 🔗 Chain of Small Steps` — the emoji is extracted and displayed separately in the UI.

### Content Sections

Content follows the H1 title. The typical structure varies by category:

- Pattern: Problem → Pattern → Example
- Anti-pattern: Problem → What Goes Wrong → Example → Solution
- Obstacle: Description → Impact

These are conventions, not enforced schemas.

## How Content Becomes Pages

The website's build process:
1. Reads each markdown file with `gray-matter` (frontmatter + content)
2. Extracts the first H1 as the page title, removing it from rendered content (one H1 per page)
3. Parses emoji and category suffix from the title
4. Renders the remaining markdown with `react-markdown`
5. Loads relationships from the centralized graph
6. Generates a static HTML page at `/{category}/{slug}/`

## Adding Content

Create a markdown file in the appropriate category directory, include `authors` frontmatter and an H1 title. The content appears on the site after the next build. Relationships are managed separately (see relationships.md).
