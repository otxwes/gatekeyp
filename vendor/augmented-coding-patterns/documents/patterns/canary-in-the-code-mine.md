---
authors: [ivett_ordog]
---

# Canary in the Code Mine

## Problem
As codebases grow and become more complex, AI agents start to perform worse. This degradation is especially pronounced when the AI is allowed to work independently for longer periods of time.

## Pattern
When you see the AI struggle with code changes, treat this as a signal that code quality is degrading. Instead of getting frustrated with the AI, ask yourself: is this codebase maintainable?

The AI's struggle is your canary - an early warning signal that code quality is declining. Use it as feedback to improve the codebase.

**When you notice the warning signs:**
1. Ask the AI to review the code, identify code quality issues, and plan a refactor
2. Review the result and provide further guidance if necessary
3. If the AI fails to sufficiently clean the code, use IntelliJ or another advanced refactoring browser to manually clean up the code

**Key insight**: AI performance degradation often indicates duplication and other maintainability issues that also make the code harder for humans to work with.

## Example

**Warning signs the canary is struggling:**

**Inconsistencies across pages**
- You ask AI to update user profile display to show new status badge
- AI updates the main profile page but misses the sidebar and settings page
- Same user info rendering logic is duplicated across multiple components
- **Signal**: Code duplication - things that should change together aren't co-located

**Running out of context**
- AI attempts to implement a feature across multiple files
- Hits context window limit and reports "I'm done"
- Tests still fail
- AI claims failures are "expected for some weird reason"
- **Signal**: Code complexity and duplication forcing AI to load too much context

**Making excuses**
- Tests fail after AI makes changes
- AI insists the failures are "expected" or "will resolve themselves"
- Contradicts itself about what's working
- **Signal**: Code is too complex for AI to reason about correctly; likely needs refactoring
