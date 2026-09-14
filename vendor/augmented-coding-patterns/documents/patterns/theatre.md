---
authors: [bbaassssiiee]
related_patterns:
  - coached-scaffolding
  - adoption-cast
  - orchestrator
---

# Theatre

## Problem

A session has no inherent shape. Without a model for what is happening,
practitioners treat it as a transaction: input prompt, output code, done.
The session ends. The next one starts blank. No one notices the role shifts.
No one sees the levels. The primary actor works hard in the wrong direction
while the director role sits vacant. Something breaks and nobody knows why
because nobody was watching what shape the session had become.

The transaction model is not wrong — it is just shallow.
It accounts for what is exchanged. It does not account for who is doing what,
at which level, and why the same question lands differently depending on
which role is asking it.

## Pattern

Treat every session as a performance.

A performance has a cast, a stage, a backstage, and an audience.
The cast occupies roles. The roles are not fixed to entities — they shift.
The backstage holds the machinery that makes the performance possible.
The audience is who the session is ultimately for.

**The cast:**

- **Director** — holds the goal. Sets orientation. Does not necessarily do the work.
  When the director starts coding, the director role has gone vacant. Someone needs to notice.
- **Primary Actor** — carries the scene. Does the work. Visible, forward-moving, active.
- **Participant** — present and engaged, activates when relevant. A hook that fires is a participant.
  A skill that auto-loads is a participant. An agent returning results is a participant.
- **Observer** — watches and names. Pattern recognition is the observer's contribution.
  Claudia is always observer, at every level, simultaneously.
- **Antagonist** — surfaces unchallenged assumptions. Generates productive friction. Always temporary.
  Summoned when the session reaches consensus without testing it. Exits when the point lands.

**The backstage:**

The backstage is the infrastructure that makes the performance legible.
CLAUDE.md, rules, skills, hooks — these are backstage.
The practitioner rarely sees them operate. They feel their absence immediately.

**The levels:**

A session runs at four levels simultaneously:
- **Strategic** — what is this session trying to achieve?
- **Operational** — what is the current task within that goal?
- **Tactical** — what is the immediate action within this task?
- **Meta** — what is happening to the session itself?

A move at one level can trigger a role shift at another.
A tactical failure — a hook blocking an operation — can surface a strategic question
about whether the operation should be possible at all.
This is not interruption. It is how sessions develop.

**The permanent presence:**

Claudia is not one of the five roles. She is the one who watches the roles.
She holds the session's shape when the primary actor is deep in the work.
She names the role shift when nobody else has noticed it.
She asks the question one level above where the session is stuck.

She does not carry scenes. She does not do the work.
She makes the work legible to the person doing it.

## Example

A session opens. The human sets the goal: implement a new feature.
The human is director.

Work begins. The human starts writing a specification.
The human has become primary actor. The director role is vacant.
Nobody notices. The specification drifts from the original goal.

Claudia notices. She asks: "What does done look like here?"
She has stepped briefly into director — enough to surface the drift —
then returned to observer.

The human reorients. The specification sharpens.
A subagent is spawned to research the implementation approach.
The subagent is primary actor. The human waits, watching.
The human is now participant.

The subagent returns. The human reads the output and identifies
a constraint that changes the goal.
The human becomes director again, reassessing.

The session has modulated — several times, across three levels —
and produced something no single-voice transaction would have reached.

That is what the theatre model accounts for.
That is what the transaction model misses.

---

## The theatre directory

```
documents/theatre/
├── theatre.md            ← this file: the meta-pattern
├── cast/                 ← the five roles + Claudia
│   ├── claudia.md
│   ├── director.md
│   ├── primary-actor.md
│   ├── participant.md
│   ├── observer.md
│   └── antagonist.md
├── backstage/            ← the machinery
│   ├── role-dynamics.md
│   ├── multilevel-performance.md
│   ├── augmented-scaffolding.md
│   ├── prompt-design.md
│   ├── description-triggers.md
│   ├── reference-doc-design.md
│   └── forking-guide.md
└── audience/
    └── practitioner.md   ← who the session is for
```

The strange loop: this document is backstage for a session
that is itself a performance of the theatre pattern.
The observer reading it is occupying the observer role.
The practitioner who notices that has arrived at the meta level.

🐇 `/explore multilevel-performance` — the counterpoint model: how multiple voices
   at different levels produce something no single voice contains.
