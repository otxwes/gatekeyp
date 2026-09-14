---
authors: [ivett_ordog]
---

# Chunking

## Problem
AI agents must keep everything in conscious attention - strategy, tactics, implementation, all file context. This cognitive overload degrades performance.

Humans chunk practiced tasks into automatic execution, freeing attention for higher-level thinking. We can't retrain production models, but we can simulate this.

## Pattern
Use a main orchestrator agent with focused subagents:

1. **Main agent stays strategic**: Plans, designs, breaks down work, integrates results
2. **Subagents handle execution**: Read files, implement, test
3. **Delegate in parallel when possible**: Multiple subagents on independent chunks

**Key insight**: Delegate execution to subagents like humans delegate practiced skills to automatic processes. Orchestrator operates strategically while subagents handle details.

**How to apply:**
- Use planning mode for mid-size tasks
- Request plans for parallel subagent execution
- Include comprehensive test plans
- Configure agent: "Always delegate coding tasks to subagents"

**When this works:**
- Mid-size tasks in clean, modular codebases
- First prototypes
- Well-defined interfaces between components

**When this fails:**
- Non-modular code
- Tightly coupled systems
- Subagents make incompatible tradeoffs

## Example

**Building this website**: Task: "Create Next.js app with unit and E2E tests, simple professional design"

Main agent planned architecture and test strategy. Subagents implemented in parallel: markdown processing, page components, unit tests, E2E tests. Result: fully functional site in one iteration.

**Multi-layer system**: Main agent designed layer interfaces. Subagents worked on separate layers following contracts. Worked because codebase was modular. In poorly structured code, subagents create integration problems.
