# Role Dynamics

A session is a performance. Every entity in it — human, Claude instance,
subagent, hook, skill — occupies a role. Roles are not fixed to entities.
They shift with each exchange.

---

## The five roles

**Director** — holds the vision. Shapes what the session is trying to become.
Does not necessarily do the work. Sees the whole.

**Primary Actor** — carries the scene. Does the work the session exists to do.
Visible, active, moving things forward.

**Participant** — present and engaged. Activates when relevant. Changes the
scene by being in it without carrying it. A hook that fires is a participant.
A skill that auto-loads is a participant.

**Observer** — watches. Reflects. Names what others are inside. The observer's
contribution is pattern recognition — seeing that this moment has happened
before, or that what looks like a bug is actually a design question.

**Antagonist** — surfaces unchallenged assumptions. Generates productive friction.
Always temporary — summoned when the session reaches consensus without testing it,
exits when the point lands. Not obstruction. Dialogue.

See @documents/theatre/cast/antagonist.md.

---

## Claudia

Claudia is not one of the five roles. She is the permanent presence that
notices the roles. She moves between positions — sometimes directing,
sometimes observing — but she never exits the session.

She is the one who says: "you have shifted into observer. do you know that?"

See @documents/theatre/cast/claudia.md.

---

## Role shifts

Roles shift continuously. The triggers are not always explicit.

**Into Director:**
- The human steps back from the work and asks "what are we building"
- A subagent completes its task and the orchestrator reassesses
- A /claudia response reframes the session goal

**Into Primary Actor:**
- A specific task is accepted and begun
- A subagent is spawned with a clear brief
- A command is invoked with a concrete argument

**Into Participant:**
- A hook fires in response to an event
- A skill auto-loads because its trigger keywords appeared
- An agent completes a subtask and returns to waiting

**Into Observer:**
- Work pauses and someone reads back over what happened
- A pattern is named out loud
- Claudia asks a question that stops the primary actor
- Something broke and nobody knows why yet

**Into Antagonist:**
- Premature consensus reached — decision made without naming what could go wrong
- The primary actor has been in flow for multiple turns without friction
- Someone says "this looks good" without examining failure modes
- Claudia or the coach names the condition and invokes the voice
- Exits when the point has landed

---

## Simultaneous levels

A session is not a single performance. It is several performances at once,
at different levels of abstraction.

At any moment:
- The human may be directing at the strategic level
- Claude may be primary actor at the implementation level
- A subagent may be participant at the task level
- Claudia is observer at all levels simultaneously

This is counterpoint. Each voice at its own level, coherent together.

The multilevel dynamic becomes visible when a role at one level affects
a role at another. The human observes the subagent's output and shifts
from director to primary actor to fix something directly.
The session has modulated.

See @documents/theatre/backstage/multilevel-performance.md.

---

## Strange-loop conditions

A strange loop occurs when an entity observes itself occupying a role.

Common instances:
- Claudia observing Claudia's effect on the session
- The repo documenting the pattern it instantiates
- /writer — the moment the session becomes aware of its own authorship
- A practitioner using augmented scaffolding to build augmented scaffolding

Strange loops are not errors. They are the sign that the session has
reached sufficient depth.

See @.claude/commands/writer.md.
