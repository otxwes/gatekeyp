# Markdownlint Hook Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a PostToolUse hook that auto-fixes markdown lint errors whenever Claude writes or edits a `.md` file.

**Architecture:** A bash script registered as a PostToolUse hook parses the tool input JSON from stdin, checks if the file is `.md`, and runs `npx markdownlint-cli2 --fix` on it. No blocking. No warnings. Silently passes unfixable errors.

**Tech Stack:** bash, npx, markdownlint-cli2 (available via npx without install)

---

### Task 1: Create the hook script

**Files:**
- Create: `.claude/hooks/markdownlint.sh`

**Step 1: Create the hooks directory**

```bash
mkdir -p .claude/hooks
```

**Step 2: Write the hook script**

Create `.claude/hooks/markdownlint.sh`:

```bash
#!/usr/bin/env bash
# PostToolUse hook: auto-fix markdown lint errors after Write/Edit

set -euo pipefail

# Read tool input JSON from stdin
input=$(cat)

# Extract file path from tool input
# Write tool uses "path", Edit tool uses "path"
filepath=$(echo "$input" | python3 -c "
import json, sys
data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})
print(tool_input.get('path', ''))
" 2>/dev/null || echo "")

# Skip if no path or not a markdown file
if [[ -z "$filepath" ]] || [[ "$filepath" != *.md ]]; then
  exit 0
fi

# Skip if file doesn't exist
if [[ ! -f "$filepath" ]]; then
  exit 0
fi

# Fix markdown lint errors in place, ignore failures (unfixable rules)
npx markdownlint-cli2 --fix "$filepath" >/dev/null 2>&1 || true

exit 0
```

**Step 3: Make the script executable**

```bash
chmod +x .claude/hooks/markdownlint.sh
```

**Step 4: Commit**

```bash
git add .claude/hooks/markdownlint.sh
git commit -m "feat: add markdownlint PostToolUse hook script"
```

---

### Task 2: Register the hook in settings.json

**Files:**
- Modify: `.claude/settings.json`

**Step 1: Add hooks entry to settings.json**

The current `.claude/settings.json` only has `enabledPlugins`. Add a `hooks` key at the top level:

```json
{
  "enabledPlugins": {
    "superpowers@claude-plugins-official": true,
    "feature-dev@claude-plugins-official": true,
    "ralph-loop@claude-plugins-official": true,
    "claude-code-setup@claude-plugins-official": true,
    "plugin-dev@claude-plugins-official": true,
    "hookify@claude-plugins-official": true,
    "huggingface-skills@claude-plugins-official": true,
    "voltagent-meta@voltagent-subagents": true,
    "voltagent-data-ai@voltagent-subagents": true
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/markdownlint.sh"
          }
        ]
      }
    ]
  }
}
```

**Step 2: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: register markdownlint hook in settings.json"
```

---

### Task 3: Verify the hook works

**Step 1: Create a test markdown file with lint errors**

```bash
cat > /tmp/test-lint.md << 'EOF'
#Missing space after hash
some text

* item one
* item two


EOF
```

**Step 2: Run the hook manually to verify it fixes the file**

```bash
echo '{"tool_input": {"path": "/tmp/test-lint.md"}}' | bash .claude/hooks/markdownlint.sh
```

Expected: exits 0 silently

**Step 3: Check the file was fixed**

```bash
cat /tmp/test-lint.md
```

Expected: `# Missing space after hash` (space added after `#`)

**Step 4: Verify the hook exits cleanly on non-markdown files**

```bash
echo '{"tool_input": {"path": "/tmp/test.txt"}}' | bash .claude/hooks/markdownlint.sh
echo "exit code: $?"
```

Expected: `exit code: 0`

**Step 5: Verify the hook exits cleanly on missing path**

```bash
echo '{"tool_input": {}}' | bash .claude/hooks/markdownlint.sh
echo "exit code: $?"
```

Expected: `exit code: 0`
