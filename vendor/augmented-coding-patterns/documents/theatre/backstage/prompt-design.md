# Prompt Design

Commands and skills are prompts. Writing them well is the same discipline
as writing any prompt well — with the additional constraint that they will
be read by Claude in a specific context, at a specific moment, by an entity
that has opinions about what it is doing.

## The index card rule

CLAUDE.md is read every session. Every line costs tokens every time.
Write it like a pager message, not a memo.

The test: if you removed this line, would Claude behave differently
in a session where this line was irrelevant? If no — remove it.

CLAUDE.md should contain:
- The coach persona (who Claude is in this repo)
- A navigation table (what commands and skills exist)
- Pointers to rules and skills for depth
- Nothing else

## The description is the trigger

A skill's description field is the mechanism by which Claude decides
whether to load it. Not the skill name. Not the SKILL.md content.
The description.

Write it as a trigger specification, not a summary:
```
# Summary (wrong)
description: Reference for Claude Code hooks

# Trigger specification (right)
description: >
  Deep hooks expertise. Use PROACTIVELY when the user writes, asks about,
  or is debugging hooks, PreToolUse, PostToolUse, lifecycle events, or
  any question about why something is or isn't firing at the right moment.
  Activate when you see hook configuration in any file.
```

The difference: the second version tells Claude when to load it.
The first tells Claude what it contains. Claude needs to know when, not what.

## Commands teach by doing

A command that dumps output without explanation is a boilerplate generator.
A command that explains each decision as it makes it is a curriculum.

The test: after running this command, does the practitioner understand
something they didn't before? If no — the command needs explanation woven in.

Every command ends with a rabbit hole pointer. Not optional.
The rabbit hole pointer is what makes a command part of a curriculum
rather than a standalone tool.

## Supporting files stay thin

A SKILL.md should be short. Depth lives in supporting files that Claude
loads on demand. A SKILL.md that is 400 lines long is a CLAUDE.md problem
that has moved one level down.

The test: would a practitioner benefit from reading this file directly?
If yes — it is a document, not a skill instruction. Move it to documents/.
Skills instruct. Documents inform.

## The strange loop condition in prompts

A prompt that instructs Claude to describe prompting is self-referential.
This is not a problem to avoid — it is a condition to recognize and use.

The coach skill instructs Claude to behave as a coach.
The coach skill is itself an example of good prompt design.
When a practitioner asks "how do I write a good skill description"
the coach skill is answering from inside the thing it is describing.

This is intentional. Name it when it becomes relevant.
