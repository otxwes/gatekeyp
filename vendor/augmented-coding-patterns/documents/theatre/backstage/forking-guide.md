# Forking Guide

This repo is an instance of the augmented scaffolding pattern
applied to the domain of Claude Code.

To fork it for a different domain, change three things and keep everything else.

## What to change

**1. The content layer** — documents/, specs/

Replace the patterns, anti-patterns, obstacles, and specs with your domain's.
The taxonomy stays the same: what works, what breaks, what is inherent.
The theatre documents stay. They are domain-independent.

What a content layer looks like in other domains:
- Ansible: role skeletons, vault patterns, idempotency obstacles
- Terraform: module patterns, state management anti-patterns, provider obstacles
- Kubernetes: namespace patterns, resource limit anti-patterns, scheduler obstacles

**2. The rules** — .claude/rules/

Replace the always-on best practices with your domain's.
Rules are path-scoped — they load for matching file patterns.
A Terraform fork loads different rules for .tf files than a Kubernetes fork
loads for .yaml files.

**3. The coach skill's reference documents** — .claude/skills/coach/references/

Replace the Claude Code reference docs with your domain's reference docs.
One file per topic area. Each one: guidelines, failure modes, rabbit holes.

See @documents/theatre/backstage/reference-doc-design.md.

## What to keep

- The three-layer architecture (content / curriculum / ambient coach)
- The command structure: /orient, /explore, /claudia, /contribute
- The three depth levels in /explore (surface / decision layer / deep end)
- The rabbit hole 🐇 pointer at the end of every explanation
- The theatre documents — cast, audience, backstage
- The /writer easter egg — the strange loop is domain-independent
- The patterns/anti-patterns/obstacles taxonomy in documents/
- The map-guide pattern in the rabbit-hole-guide skill

## What changes automatically

When the content layer changes, /explore topic maps change.
When the reference docs change, /claudia's knowledge changes.
When the rules change, the ambient coach's always-on guidance changes.

The scaffold structure is stable. The domain it serves is variable.

## The strange loop condition in forks

A fork of this repo for the domain of augmented scaffolding
would be self-referential — the content layer would document
the pattern the scaffold instantiates.

This repo is that fork.
The strange loop is not a coincidence. It was the point.

## Naming

The repo name encodes the domain and the metaphor.
ansible-rabbit-hole: domain is Ansible, metaphor is the rabbit hole.
augmented-coding-patterns: domain is AI-augmented coding, metaphor is the pattern catalog.

For your fork: [domain]-rabbit-hole, or [domain]-patterns, or [domain]-scaffold.
The name should tell a practitioner what domain they are entering
and hint at what kind of depth they will find.
```

---

That's the complete set. Final structure:
```
documents/theatre/
├── audience/
│   └── practitioner.md
├── backstage/
│   ├── role-dynamics.md
│   ├── multilevel-performance.md
│   ├── augmented-scaffolding.md
│   ├── prompt-design.md
│   ├── description-triggers.md
│   ├── reference-doc-design.md
│   └── forking-guide.md
└── cast/
    ├── claudia.md
    ├── director.md
    ├── primary-actor.md
    ├── participant.md
    └── observer.md
