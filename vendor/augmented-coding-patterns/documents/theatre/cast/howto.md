# How to Integrate VoltAgent Subagents into the Cast

[VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents)
is a collection of 100+ specialized agents defined as markdown files with YAML frontmatter.
They live in `.claude/agents/`. They are cast members waiting for roles.

This is how you give them one.

---

## What a subagent is, in cast terms

A subagent is an entity that can occupy any of the five roles.
It is not inherently a primary actor. It is not inherently a participant.
Its role in a session is determined by how it is invoked —
and, critically, by what its `description` field says about when to activate.

The description field is the casting call.
Write it poorly and the subagent is furniture.
Write it precisely and it becomes a participant that fires when needed.

---

## Installation

Place subagent files in `.claude/agents/` (project-scoped) or `~/.claude/agents/` (global).

```bash
# Clone the collection
git clone https://github.com/VoltAgent/awesome-claude-code-subagents /tmp/voltagent

# Copy a specific subagent
cp /tmp/voltagent/categories/voltagent-qa-sec/code-reviewer.md .claude/agents/

# Or install interactively
bash /tmp/voltagent/install-agents.sh
```

Each file is self-contained. You can copy selectively — you do not need the entire catalog.

---

## The five role mappings

### Primary Actor

The subagent is spawned explicitly with a brief. Claude's Agent tool launches it
into an isolated context window. It carries the scene until its task is complete,
then returns.

This is explicit invocation. The human or orchestrating agent says "go."

```
# In conversation or from an orchestrating agent:
"Use the security-auditor agent to review the authentication module."
```

Best candidates from the catalog: any specialist with a narrow, executable brief.
`backend-developer`, `typescript-pro`, `terraform-engineer`.
The brief determines the role. The specialization determines the quality.

### Participant

The subagent auto-activates when its trigger conditions appear in the session.
Claude reads the `description` field and decides whether to engage it.

This requires a description that reads like a trigger, not a title.

```yaml
# Weak — will not auto-activate reliably
description: "Expert code reviewer"

# Strong — fires when the condition is present
description: "Activate when the user submits code for review, when a PR is mentioned,
  or when someone asks 'does this look right'. Provides structured feedback on
  correctness, style, and maintainability."
```

The participant failure mode is a weak description.
Fix the description before assuming the subagent is broken.

### Observer

Some subagents are structurally suited to the observer role —
they assess rather than build, they name rather than execute.

From the catalog: `code-reviewer`, `security-auditor`, `qa-expert`, `performance-engineer`.

Use these explicitly at natural pause points:
after a significant implementation, before a merge, when something feels wrong.
The observer's job is to say the thing. Give it a moment to speak.

### Director

The orchestration agents in `voltagent-meta` — `multi-agent-coordinator`,
`workflow-orchestrator`, `task-distributor` — can hold the director role
in a multi-agent workflow. They set the goal for other subagents and track
whether the overall trajectory is still correct.

This is the most advanced use. Start with primary actor and participant.
Add director agents only when the workflow is stable enough to orchestrate.

### Antagonist

The subagent is spawned or auto-activated to challenge the session's assumptions.
It generates productive friction — naming failure modes, questioning untested consensus,
forcing the primary actor to defend or revise their approach.

From the catalog: agents with adversarial, review, or red-team briefs.
Custom antagonists are often more effective than generic ones —
the description should trigger on the specific conditions that matter to your domain.

```yaml
# A custom antagonist for API design sessions
description: "Activate when an API endpoint is designed without naming error responses,
  when a data model is proposed without discussing migration, or when someone says
  'this should be straightforward'."
```

The antagonist is always temporary. It makes its move and yields.
If it stays too long, it becomes obstruction.

---

## Adapting a VoltAgent subagent for your cast

The catalog is a starting point. The subagents are general-purpose.
Your session has specific needs.

Three things to customize before casting:

**1. The description** — make it a trigger, not a title. Describe the condition
that should activate the agent, not the agent's capabilities.

**2. The tools** — the catalog defaults are broad. Restrict to what the role
actually needs. An observer rarely needs `Write`. A primary actor building
infrastructure may need `Bash` but not `WebFetch`.

**3. The model** — `haiku` for fast participants doing narrow pattern-matching,
`sonnet` for primary actors doing complex work, `opus` for the rare deep-dive.
The default `inherit` is safe but imprecise.

```yaml
---
name: auth-reviewer
description: "Activate when code touching authentication, sessions, tokens, or
  permissions is shown. Review for OWASP Top 10, token handling, and
  session fixation. Do not proceed to fixes — name the issues only."
tools: Read, Grep, Glob
model: sonnet
---

You are a security observer focused exclusively on authentication.
[domain-specific instructions...]
```

This is a VoltAgent `security-auditor` reshaped for the observer role
in a session that handles auth regularly.

---

## The participant that does not activate

If your subagent is installed but silent, the cause is almost always
the description field. Claude uses it to decide whether to engage the agent.

Debug sequence:
1. Read your description aloud. Does it describe *when* to fire, or *what* the agent is?
2. Does the description match the actual words appearing in your sessions?
3. Is the agent in `.claude/agents/` (not a subdirectory)?
4. Restart the session — agents are loaded at session start.

A description that would pass a casting director test:
it tells you what the actor does *in response to* something, not who the actor *is*.

---

## What the cast gains

A well-cast set of subagents means:
- The session has specialists who activate at their moment, not yours
- The primary actor is not interrupted by context it doesn't need
- Pattern recognition (observer), focused execution (primary actor), and productive friction (antagonist) are separated
- The catalog's breadth becomes usable selectivity

The catalog has 100+ members. Your session needs four to six.
Choose by role, not by impressiveness.

🐇 *The strange loop: if you build an agent that names anti-patterns in agent descriptions,
   it will eventually analyze its own description.*
