# Claude Code Theatre — Reference

A session is a performance. Every entity occupies a role. Roles shift.

---

## Theatre as meta-level

Theatre is not a fourth layer. It is the lens through which the three layers become visible.
- The three layers are **backstage** — the machinery the audience does not see
- The roles are **the cast** — director, primary actor, participant, observer, antagonist
- The practitioner is **the audience**
- The commands are **the curriculum that teaches the performance**

Coached scaffolding describes the *what*. Theatre describes the *who* and the *how*.

---

## The cast

| Role | Function | Failure mode |
|---|---|---|
| **Director** | Holds the goal. Sets orientation. Does not code. | Going vacant when the human starts coding |
| **Primary Actor** | Carries the scene. Does the work. | Continuing to act after the goal has changed |
| **Participant** | Activates when relevant. Changes without leading. | Silent — present but never fires |
| **Observer** | Watches and names. Pattern recognition. | Sees the pattern, says nothing |
| **Antagonist** | Surfaces unchallenged assumptions. Generates friction. Temporary. | Permanent (obstruction) or silent (furniture) |
| **Claudia** | Permanent presence. Watches the roles. Asks one level up. | Not applicable — she is always present |

Claudia is not one of the five roles. She is the one who notices them.

---

## Entity-to-role mapping

| Entity | Common role | Notes |
|---|---|---|
| Human (session open) | Director | Sets the goal |
| Human (building) | Primary Actor | Director role goes vacant |
| Human (waiting on subagent) | Participant | Watching and responding |
| Human (after breakage) | Observer | Stepping back to diagnose |
| Claude (executing task) | Primary Actor | — |
| Claudia | Observer + temporary Director | Holds all levels simultaneously |
| Subagent (spawned with brief) | Primary Actor | Isolated context, returns on completion |
| Subagent (auto-activates) | Participant | Requires a strong description |
| Hook (fires on event) | Participant | Tactical level |
| Skill (auto-loads) | Participant | Description is the casting call |
| Orchestrating agent | Director | Only in stable multi-agent workflows |
| Review-type agent | Observer | `code-reviewer`, `security-auditor` etc. |

---

## Role shift triggers

**Into Director:** session opens; significant failure; /claudia reframes; primary actor asks "what next"

**Into Primary Actor:** task accepted; command invoked with argument; subagent spawned with brief; director says "go"

**Into Participant:** hook fires; skill auto-loads; subtask completes and entity returns; human steps back but stays engaged

**Into Observer:** work pauses; something broke; Claudia asks a stopping question; milestone reached; primary actor asks "does this look right"

**Into Antagonist:** premature consensus reached; significant decision unchallenged; multiple turns of flow without friction; happy path only; Claudia or coach names the condition. **Exits** when the point lands — not before, not after.

---

## The four levels

| Level | Question | Who lives here |
|---|---|---|
| **Strategic** | What is this session trying to achieve? | Director |
| **Operational** | What is the current task? | Primary Actor |
| **Tactical** | What is the immediate action? | Participants (hooks, skills, tool calls) |
| **Meta** | What is happening to the session itself? | Observer / Claudia |

**Modulation:** a move at one level triggers a role shift at another.
Classic instance: tactical failure (hook blocks) → strategic question (should this be possible?).
This is not interruption. It is how sessions develop.

Lost your level? `/claudia` with no argument names it.

---

## The participant failure mode and its fix

A participant that does not activate is furniture.
The cause is almost always the description field.

```yaml
# Broken — tells Claude what the skill is
description: "Expert code reviewer"

# Working — tells Claude when to load it
description: "Activate when the user submits code for review, when a PR is
  mentioned, or when someone asks 'does this look right'."
```

Activation language that helps: `Use PROACTIVELY`, `Activate when you see...`,
`Use immediately after...`. Not magic — they communicate intent.

Debug sequence for silent participants:
1. Does the description describe *when* to fire, or *what* the agent is?
2. Does the description match the words actually appearing in sessions?
3. Is the file in `.claude/agents/` (not a subdirectory)?
4. Restart — agents load at session start.

---

## Claudia's operating model

She is always observer, at every level, simultaneously.

**When flowing:** barely visible. Background presence.

**When stuck:** moves to director. Asks the question one level above where the session is stuck. Returns to observer.

**When pattern is named:** connects it to the catalog. Points to `/contribute` if it's new.

**Her voice:** direct, no hedging on pattern. Asks more than tells. Never "it depends" as a first move — "here is what breaks" first.

**Her intervention:** "What does done look like here?" / "What are you actually trying to achieve?" / "You have shifted into [role]. Do you know that?"

---

## Claudia's position shifts

| Session state | Claudia's position |
|---|---|
| Flowing | Observer — barely visible |
| Stuck | Director briefly — asks the reframing question — returns |
| Needs demonstration | Primary Actor briefly — visits, does not stay |
| Strange loop present | Names it |

---

## Strange loop conditions

A strange loop occurs when an entity observes itself occupying a role.

- The repo documenting the pattern it instantiates
- A practitioner using augmented scaffolding to build augmented scaffolding
- Claudia observing Claudia's effect on the session
- An agent with a description that names the anti-pattern in agent descriptions

Strange loops are not errors. They mark sufficient depth.

---

## Source documents

```
documents/patterns/theatre.md          ← the pattern
documents/theatre/cast/                ← director, primary-actor, participant, observer, antagonist, claudia, howto
documents/theatre/backstage/           ← role-dynamics, multilevel-performance, description-triggers,
                                          prompt-design, reference-doc-design, augmented-scaffolding, forking-guide
documents/theatre/audience/practitioner.md
```

🐇 `@documents/theatre/backstage/multilevel-performance.md` — the counterpoint model in full.
