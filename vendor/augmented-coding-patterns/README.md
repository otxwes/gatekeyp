# Augmented Coding Patterns — Coached Scaffolding Fork

> *"I knew who I was this morning, but I've changed a few times since then."*
> — Alice

This is a fork of [lexler/augmented-coding-patterns](https://github.com/lexler/augmented-coding-patterns) — a catalog of patterns, anti-patterns, and obstacles for developing software with LLMs.

**What's different here:** This fork adds a three-layer coaching architecture that turns the pattern catalog into a live learning environment. The repo doesn't just document AI-augmented coding — it *demonstrates* it. You learn by doing, coached by the system you're learning about.

The pattern this fork embodies is called **Coached Scaffolding**.

---

## The architecture

```
Layer 1 — CONTENT
  documents/patterns/         what works and why
  documents/anti-patterns/    what breaks and how
  documents/obstacles/        inherent limitations to know about

Layer 2 — CURRICULUM
  .claude/commands/           /orient  /explore  /claudia  /contribute
  .claude/skills/             coach, storyteller, rabbit-hole-guide (auto-triggered)

Layer 3 — AMBIENT COACH
  CLAUDE.md                   the index card Claude always reads
  .claude/rules/              always-on best practices (path-scoped)
  .claude/skills/             specialists loaded on demand
```

The content is the original fork. The curriculum and ambient coach are what this fork adds.

---

## How to use it

Open this repo in [Claude Code](https://claude.ai/code). The coaching activates automatically.

| Command | What it does |
|---|---|
| `/orient` | Find your starting point |
| `/explore <concept>` | Follow a concept three levels deep |
| `/claudia` | Deep coaching — picks up current context automatically |
| `/contribute` | Add a pattern, anti-pattern, or obstacle |

Start with `/orient` if you're new. Start with `/claudia` if you already know what you want to dig into.

---

## The strange loop

This repo documents how to augment coding with AI.
The repo itself is augmented by AI using the patterns it documents.
When you add a pattern here, you are teaching the coach.
When the coach teaches you, it may surface a pattern worth adding.

The loop closes in `/contribute`.

---

## What's in the catalog

- **60+ patterns** — ground-rules, feedback-loop, focused-agent, context-management, hooks, orchestrator, and more
- **9 anti-patterns** — ai-slop, silent-misalignment, unvalidated-leaps, and more
- **13 obstacles** — hallucinations, context-rot, compliance-bias, non-determinism, and more

Browse the [live site](https://lexler.github.io/augmented-coding-patterns/) for the upstream catalog, or explore locally through Claude Code with the commands above.

---

## Contributing

See [CONTRIBUTE.md](./CONTRIBUTE.md) for the full guide.

**In Claude Code:** run `/contribute` for an interactive workflow that walks you through the process step by step.

---

## Forking this fork

The coaching architecture is itself a pattern: `documents/theatre/backstage/augmented-scaffolding.md`

If you want to apply this architecture to a different domain, see `documents/theatre/backstage/forking-guide.md`.
