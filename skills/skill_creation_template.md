---
name: skill-creation-template
description: A standard template and guide for creating new skills to ensure a repeatable development process.
---

# Skill Creation Process

To maintain consistency in our project, all new "Skills" (specialized instruction sets) should be created using the following structure. This ensures that I can quickly switch into the correct context when you call upon a specific skill.

## Standard Structure
Every skill file must include:
1.  **YAML Frontmatter:**
    - `name`: A unique, lowercase, hyphenated identifier (e.g., `security-audit`).
    - `description`: A clear summary of what the skill does and when to use it.
2.  **Title:** A clear heading for the skill name.
3.  **Instructions:** A detailed list of steps or rules I must follow when this skill is active.
4.  **Guidelines:** High-level principles or "rules of thumb" to maintain quality.
5.  **Examples:** Sample interactions to demonstrate how the skill should be applied in practice.

## How to Create a New Skill
1.  Identify a recurring task or a specific area that requires a consistent "mindset" (e.g., "Database Optimization," "Documentation Writing").
2.  Create a new file in the `skills/` directory.
3.  Use the format below as your template:

---

### [Skill Name]

## Instructions
[List specific steps...]

## Guidelines
[List core principles...]

## Examples
- User: [Input]
- Assistant: [Output based on skill rules]

---

## Current Active Skills
- `security_audit.md` (Security & Privacy)
- `ui_ux_design.md` (Aesthetics & UX)
