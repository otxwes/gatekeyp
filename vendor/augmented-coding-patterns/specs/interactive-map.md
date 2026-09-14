# Interactive Map

The project includes a visual map designed for a talk presentation. It provides a guided path through a curated subset of the patterns collection.

## Talk Path

There are two versions of the talk: the original (27 items) and a longer masterclass (32 items). The map currently reflects the 27-item version and hasn't been updated to 32 yet.

Both are organized into three sections:

Section 1 — Context Management: How to set up and maintain context for AI
- Foundations (cannot-learn, context-rot, context-management, knowledge-document, ground-rules, extract-knowledge)
- Focus (limited-context-window, distracted-agent, limited-focus, focused-agent, references, knowledge-composition)
- Noise (excess-verbosity, semantic-zoom, noise-cancellation)

Section 2 — Reliability: How to get consistent, correct results
- Non-Determinism (non-determinism, knowledge-checkpoint, parallel-implementations, offload-deterministic)
- Hallucinations and Complexity (hallucinations, perfect-recall-fallacy, playgrounds, unvalidated-leaps, degrades-under-complexity, chain-of-small-steps)
- Forcing Compliance (hooks, reminders)

Section 3 — Steering: How to keep AI aligned with your intent
- black-box-ai, compliance-bias, silent-misalignment, active-partner, check-alignment, context-markers, answer-injection, tell-me-a-lie, reverse-direction, text-native

The sequence is defined in `/talk_path.md`. Not all patterns in the collection are part of the talk.

## Map Feature

The `/talk/` page on the website renders the talk path as an interactive canvas-based map. Each pattern is positioned according to coordinates in `website/public/maps/map-index.json`. Clicking a pattern opens its content in a modal.

The map is linked to a YouTube guided walkthrough of the talk.
