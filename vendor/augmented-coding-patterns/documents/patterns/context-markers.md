---
authors: [lada_kesseler]
---

# Context Markers

## Problem
AI context is invisible. Can't tell what rules AI is following, whether it read your ground rules, or if context has degraded.

## Pattern
Use visual markers (emojis) to signal active context:
- Start every response with a marker showing current mode
- Different markers for different contexts/roles
- Stack markers when multiple contexts active
- Special markers for specific actions (errors, re-reads)
- Can be impromptu one-offs for crucial instructions (when adding an important instruction mid-conversation,
  ask it to reply to you with an additional emoji)

Makes the invisible parts of context visible at a glance.

## Example
Some example markers:
- 🍀 = ground rules have been read
- 🔴/🌱/🌀 = Shows specific TDD (red|green|refactor) phase and that it read tdd.md process file
- ✅ = committer role active
- ❗️ = flagging an error
- ♻️ = rules just re-read
- ✨📂 = creating new repository

**How to set this up**

In ground rules (user level):
```markdown
  **ALWAYS** start replies with STARTER_CHARACTER + space (default: 🍀). Stack emojis when requested, don't replace.
```
  
In specialized contexts (committer):
```markdown
When I tell you're a committer, add ✅ to STARTER_CHARACTER emojis. Make sure there's a space between any emojis and the text
```

In process files (TDD):
```
STARTER_CHARACTER = 🔴 for red test, 🌱 for green, 🌀 when refactoring, always followed by a space
```
 
This way let them stack:
"🍀 ✅" = base rules loaded + committer role active. Easy to see what context AI is operating under.
