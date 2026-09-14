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
