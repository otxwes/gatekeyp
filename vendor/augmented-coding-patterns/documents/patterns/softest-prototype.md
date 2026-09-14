---
authors: [lada_kesseler]
---

# Softest Prototype

## Problem
Code constrains too early. You don't know what you need until you've built it.
But building takes time, and wrong decisions are expensive to change.

## Pattern
AI + files is softer than software.
Use AI as a flexible agent with markdown instructions instead of code.
Discover what you need by using it, not by planning it. Very powerful when you're not sure what you need.

The "system" is just:
- Markdown files with instructions
- AI reading and following them
- Conversation to adjust as you go

Shape the solution while using it. Pivot instantly. No compile, no refactor.
Allows exploring solution space by using it before you write a single line of code.

## Example
**Zork AI**: Instead of coding game integration, used tmux + AI tools. Discovered needs (how to do map, memory) while playing.

**Review workflow**: Markdown inputs → AI processing → formatted output. System emerged through use.

The power: You're running before you know what you're building. Can validate approach and learn about the solution space.
