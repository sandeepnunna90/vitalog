#!/usr/bin/env bash
# PreToolUse (Bash) — fires before every Bash tool call.
# Acts only when the command is `git commit`; silently exits otherwise.
set -euo pipefail

input=$(cat)
cmd=$(echo "$input" | jq -r '.tool_input.command // ""')

if ! echo "$cmd" | grep -q 'git commit'; then
  exit 0
fi

ruff check . && ruff format --check . && uv run mypy .
