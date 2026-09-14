# Markdownlint PostToolUse Hook

## Summary

Auto-fix markdown lint errors whenever Claude writes or edits a `.md` file. No blocking. No warnings. Fix what can be fixed, silently pass the rest.

## Hook

- **Event:** `PostToolUse`
- **Matcher:** `Write|Edit`
- **Command:** `.claude/hooks/markdownlint.sh`

## Script logic

1. Parse stdin JSON to extract `tool_input.path` (Write) or `tool_input.path` (Edit)
2. If path does not end in `.md` → exit 0
3. Run `npx markdownlint-cli2 --fix <path>`
4. Exit 0 always

## Settings registration

```json
"hooks": {
  "PostToolUse": [{
    "matcher": "Write|Edit",
    "hooks": [{"type": "command", "command": ".claude/hooks/markdownlint.sh"}]
  }]
}
```

## Files to create/modify

- `.claude/hooks/markdownlint.sh` — new hook script
- `.claude/settings.json` — add hooks entry

## Decisions

- PostToolUse (not PreToolUse) — can fix in place after write, no content injection needed
- `--fix` only — unfixable rules silently pass, no noise
- No `.markdownlint.json` config — use markdownlint-cli2 defaults
