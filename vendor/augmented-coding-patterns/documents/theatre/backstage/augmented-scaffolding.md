# Augmented Scaffolding

Augmented scaffolding is the pattern this repo embodies.
It is a scaffold that works in both directions simultaneously.

## The scaffold

A scaffold is a temporary structure that makes construction possible.
You build the scaffold so you can build the building.
When the building is done, the scaffold comes down.

Augmented scaffolding does not come down.
It is the structure and the thing built on it simultaneously.

## Two directions, one structure

**Builder's direction** (git history, repo construction):
Content is laid first. Curriculum is built on content. The ambient coach
is built on curriculum. Each layer depends on the layer below.
This is the order of construction — the order visible in commit history.

**Practitioner's direction** (LLM dialogue, session):
The ambient coach is encountered first. It routes to curriculum.
Curriculum points to content. The practitioner descends.
This is the order of experience — the order visible in a session transcript.

The scaffold is identical in both directions. The direction of travel differs.
The builder ascends. The practitioner descends. Same structure.

## The three layers

**Content** — documents/, specs/, theatre/
What is known. Patterns, anti-patterns, obstacles. The domain's encoded decisions.
Built first. Descended to last.

**Curriculum** — .claude/commands/
How to learn. Commands that teach by doing. Each one ends with a rabbit hole pointer.
Built on content. The practitioner's first entry point.

**Ambient coach** — CLAUDE.md + .claude/rules/ + .claude/skills/
Who is present. Always active. Holds context. Routes to curriculum and content.
Built last. The practitioner encounters it first.

## What makes it augmented

A scaffold built by one person for others to climb is construction.
A scaffold that adjusts to the climber — that Claudia notices where they are
and offers the next rung — is augmented.

The augmentation is not magic. It is:
- The coach skill reading the session and routing to the right reference
- The description triggers loading the right skill for the current context
- Claudia asking the question that makes the next rung visible
- /contribute keeping the scaffold current as the domain evolves

## The scaffold and the strange loop

When the domain of the scaffold is scaffolding itself —
when the content layer documents the pattern that the scaffold instantiates —
the scaffold refers to itself.

This is not a defect. It is the condition that makes /writer meaningful.

See @documents/theatre/backstage/role-dynamics.md for the strange-loop condition.
See @.claude/commands/writer.md for the moment it becomes visible.
