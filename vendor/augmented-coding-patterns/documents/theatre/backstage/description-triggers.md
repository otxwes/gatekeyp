# Description Triggers

The description field in a skill's YAML frontmatter is the only mechanism
by which Claude decides whether to auto-load the skill.

This is the most misunderstood part of skill design.
Most skills that "don't work" have a description problem.

## How it works

Claude reads the session context — the user's message, recent history,
active files. It compares this against skill descriptions.
If the description matches the context, the skill loads.

Claude is not doing keyword matching. It is doing semantic similarity.
But semantics only work if the description contains the right concepts.
A description that doesn't mention the concepts it covers will not match
sessions that involve those concepts.

## The passive description failure
```yaml
# This skill will almost never auto-load
description: Claude Code reference documentation

# This skill loads when it should
description: >
  Deep Claude Code expertise. Use PROACTIVELY when the user writes,
  reviews, debugs, or asks about CLAUDE.md, skills, commands, agents,
  subagents, hooks, settings, or permissions. Activate when you see
  YAML frontmatter, settings.json, hook configuration, or any question
  about why Claude Code is not behaving as expected.
```

The first description tells Claude what the skill contains.
The second tells Claude when to load it, with specific trigger concepts,
explicit activation language, and concrete examples of the contexts
where it belongs.

## Activation language

Certain phrases increase the probability of auto-loading:
- "Use PROACTIVELY" — signals that Claude should not wait to be asked
- "MUST BE USED" — stronger signal, use for critical skills
- "Activate when you see..." — gives Claude a concrete pattern to match
- "Use immediately after..." — ties activation to a specific event

These are not magic words. They work because they communicate intent
clearly to a model that is trying to infer intent.

## The coverage test

For each concept the skill covers, ask: does the description contain
that concept explicitly, or a close semantic neighbor?

If a skill covers PreToolUse hooks but the description says only "hooks" —
a session about PreToolUse may not load it. Add "PreToolUse" to the description.

The description should be a complete map of the skill's trigger space.
Not exhaustive — but representative enough that no major use case is invisible.

## User-invoked skills

Setting `user_invoked: true` in frontmatter means the skill only loads
when explicitly called with /skill-name. Use this for:
- Destructive operations that require explicit intent
- Long-running tasks where auto-loading would be disruptive
- Easter eggs

Do not use user_invoked as a way to avoid writing a good description.
A skill that should auto-load but doesn't because its description is passive
is not a user-invoked skill — it is a broken skill.
