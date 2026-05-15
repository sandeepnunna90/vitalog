#!/usr/bin/env bash
# PostToolUse (Bash) — fires after every Bash tool call.
# Acts only when the command was `gh pr create`; silently exits otherwise.
set -euo pipefail

input=$(cat)
cmd=$(echo "$input" | jq -r '.tool_input.command // ""')

if ! echo "$cmd" | grep -q 'gh pr create'; then
  exit 0
fi

pr_url=$(echo "$input" | jq -r '.tool_response.stdout // ""' \
  | grep -oE 'https://github\.com/[^/]+/[^/]+/pull/[0-9]+' \
  | head -1)
pr_num=$(echo "$pr_url" | grep -oE '[0-9]+$')

if [ -z "$pr_num" ]; then
  exit 0
fi

jq -n --arg num "$pr_num" --arg url "$pr_url" \
  '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":("PR #" + $num + " was just opened (" + $url + "). Immediately invoke the pr-review-expert skill to review it. When the review is complete, post the full review as a GitHub PR comment by running: gh pr review " + $num + " --comment --body with the complete review text. Do not truncate the review.")}}'
