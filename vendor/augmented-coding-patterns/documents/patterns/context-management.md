---
authors: [lada_kesseler]
---

# Context Management

## Problem
AI has no persistent memory and context degrades over time.

## Pattern
Treat context as a scarce, degrading resource that requires active management.
You have only two operations: **append to context** (prompt it) and **reset it** (start a new conversation). Everything you do with AI works within this constraint.