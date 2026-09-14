---
authors: [bbaassssiiee]
---

# Adoption Cast

## Problem
Teams adopting AI-augmented coding repeat predictable failures. Without shared names for the failure modes, you can't call them out in code review or warn against them before they ship.

## Pattern
Name the archetypes. Use them as diagnostic shorthand — one word instead of three paragraphs.

Six archetypes appear in every adoption:

- **Pooh** — cargo-culter. Copies a CLAUDE.md from a blog post, adjusts the project name, ships it. Configuration is configuration to Pooh, not a prompt.
- **Eeyore** — earned pessimist. Names the failure mode before it happens. Undervalued until it arrives.
- **Rabbit** — correct structure, inaccessible architecture. Everything is coherent and undocumented and lives in Rabbit's head.
- **Tigger** — enthusiasm that breaks things. Reaches for subagents and parallelism for the wrong reasons. Moves on before fixing what broke.
- **Kanga** — methodical, validates, saves the team. Writes the test before the hook. Correct about trailing slashes six months later.
- **Christopher Robin** — reframes. Asks the obvious question no one else said aloud.

## Example

Code review: "This is Rabbit's architecture — correct but inaccessible. Can we document the intent?"

Retrospective: "We went full Tigger on the agent layer. Three rewrites, nothing shipped. Christopher Robin's question: what are we actually trying to do?"
