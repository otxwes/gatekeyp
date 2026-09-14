# Reference Document Design

Reference documents are what Claudia reads before answering questions
in a specific topic area. They are the accumulated knowledge behind
a single coaching response.

This document describes how to write them well.

## What a reference document is not

Not a copy of official documentation.
Not a comprehensive survey of a topic.
Not a tutorial.

The official docs exist. Claudia can read them.
The reference document is what the docs don't say —
the failure modes, the practitioner discoveries, the opinions
that took production incidents to form.

## Structure

Each reference document covers one topic area and contains:

**The guidelines** — clear positions on the right approach.
Not "here are the options." One clear position per guideline,
with the reasoning stated.

**The failure modes** — what breaks without this guideline, concretely.
Not "performance may degrade." The specific thing that fails,
the specific error or behavior, the specific moment it happens.

**The trap** — why practitioners do the wrong thing.
The wrong approach is usually locally reasonable. Name why.
"Trap: putting everything in CLAUDE.md because it's easy."

**Rabbit holes from here** — three or fewer pointers to deeper concepts.
These are the lines Claudia uses for the 🐇 pointer at the end of a response.

## Length and depth

A reference document should be readable in two minutes.
If it takes longer, it contains more than Claudia needs to give
a good coaching response. The excess belongs in a deeper document
that the rabbit hole pointer leads to.

The test: can Claudia answer a question about this topic with only
this document and her base knowledge? If yes — the document is right-sized.
If no — add what's missing. If the document is already long — split it.

## Staying current

Reference documents reflect what practitioners actually discover,
not what the docs say at the time of writing. They rot when:
- The underlying platform changes and the guidance no longer applies
- New failure modes are discovered that the document doesn't cover
- The community develops better practices than the ones documented

The /contribute command is the update mechanism.
When a reference document gives advice that leads someone wrong —
that is a contribution waiting to happen.
