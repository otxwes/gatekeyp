---
authors: [lada_kesseler]
---

# Cast Wide

## Problem
Don't settle for your first solution. Actively push AI to show you more alternatives.

Your first solution comes from your limited knowledge and is prone to answer injection.

AI is extremely well-read; it knows approaches you've never encountered, entire solution categories you're either not familiar with or not even thinking about.

Settling for first means missing a lot of possible alternatives outside your bubble.

## Pattern
After discussing your initial approach, deliberately look for blind spots:
- "What alternative solutions to the same problem might be possible that we haven't even considered?"
- "What are we not even thinking about?"
- "What should I be thinking about that I'm not considering at all regarding this problem?"
- "Can we simplify this?.." -> "Could we go simpler than even that?"

Iterating several times and running several parallel explorations with different coding agents makes it even more powerful.

## Example
During a hackathon, needed to process emails from external clinics and extract data.
Asked AI: "How do we read Outlook emails?" Standard answer: Microsoft Graph API with OAuth2 and Azure AD registration. A lot of busywork.
Pushed for simpler: "What's the simplest way?" → IMAP with basic auth. Better, but still network protocols and parsing.
Kept pushing: "Even simpler?" → File monitoring emerged: configure Outlook to save emails to a folder, process as files. Zero network complexity. 

Discovered an entire category we hadn't considered: file-based processing instead of API solutions. This made a big difference in time spent setting it up. 
In the end, contributed to getting the project funding because it freed the team up to focus on important parts.
The context didn't warrant any more complexity than that, it needed to work on one person's computer.
