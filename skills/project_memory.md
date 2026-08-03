---
name: project-memory
description: Durable project guidance memory. Use before starting any task to check for relevant lessons, and after completing tasks to record new lessons learned. Ensures the project continuously improves through accumulated knowledge.
---

# Project Memory Skill

This skill governs the use and maintenance of the project's durable memory system, stored in `docs/project_memory.md`.

## Instructions

### Before Starting a Task

1. **Skim `docs/project_memory.md`** for relevant lessons that may apply to the current task.
2. **Check the Self-Improvement Log** (Section 5) for recent learnings that might be relevant.
3. **Check Tooling Solutions** (Section 1) if you're using a tool that has known issues or workarounds.
4. **Check Process Improvements** (Section 2) for workflow best practices.

### During a Task

1. **If you hit an error**, check if the solution is already documented in `docs/project_memory.md`.
2. **If you discover a new workaround or solution**, note it mentally — you'll add it to the memory after the task.
3. **If you find a documented solution is outdated or incorrect**, note that too.

### After Completing a Task

1. **Review what you learned** during the task.
2. **Add new lessons** to the appropriate section of `docs/project_memory.md`:
   - Tool errors and their solutions → Section 1 (Tooling Solutions & Error Fixes)
   - Process inefficiencies and improvements → Section 2 (Process Improvements)
   - Coding practices and patterns → Section 3 (Coding Practices)
   - New project knowledge → Section 4 (Project-Specific Knowledge)
3. **Add a new entry to the Self-Improvement Log** (Section 5) with:
   - Date
   - What was done
   - Lessons learned
   - Next steps
4. **Keep entries concise and actionable** — a future reader should be able to apply the lesson immediately.

## Guidelines

- **Always update the memory after significant tasks** — this is how the project improves.
- **Be specific** — include exact commands, error messages, and solutions.
- **Don't duplicate** — check if a lesson already exists before adding it.
- **Update, don't append blindly** — if a lesson is outdated, update it rather than adding a conflicting entry.
- **The memory is for the project, not just for you** — write for future developers and AI assistants.

## Examples

### Example 1: Recording a Tool Error

**User**: "I keep getting an error with the safety pre-commit hook."

**Assistant**: Checks `docs/project_memory.md` Section 1.2, finds the documented issue with `pyupio/safety`, and applies the documented workaround (use `pip-audit` instead).

### Example 2: Recording a New Lesson

**User**: "I found that `uv run pytest` is much faster than `python -m pytest`."

**Assistant**: Adds this to Section 1.1 (uv) in `docs/project_memory.md` and updates the Self-Improvement Log.

### Example 3: Checking for Relevant Lessons

**User**: "Let's add a new dependency."

**Assistant**: Checks `docs/project_memory.md` for supply chain audit lessons, then runs `uv add <package>` and `uv run pip-audit` to verify the new dependency is safe.
