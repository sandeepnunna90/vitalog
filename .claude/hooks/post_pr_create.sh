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
# Extract owner/repo from URL: https://github.com/OWNER/REPO/pull/N
repo_path=$(echo "$pr_url" | grep -oE 'github\.com/[^/]+/[^/]+' | sed 's|github\.com/||')

if [ -z "$pr_num" ]; then
  exit 0
fi

jq -n --arg num "$pr_num" --arg url "$pr_url" --arg repo "$repo_path" \
  '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":("PR #" + $num + " was just opened (" + $url + "). Immediately invoke the pr-review-expert skill to review it. When the review is complete, post it as a single GitHub review using the API — do NOT use gh pr review --comment. Use this command structure:\n\ngh api repos/" + $repo + "/pulls/" + $num + "/reviews --method POST \\\n  --field event=COMMENT \\\n  --field body='"'"'<overall summary: blast radius, security verdict, test coverage delta, looks-good items>'"'"' \\\n  --field '"'"'comments[][path]=src/foo.py'"'"' --field '"'"'comments[][line]=42'"'"' --field '"'"'comments[][body]=<finding text>'"'"'\n\nRules:\n- Findings that cite a specific file:line (e.g. src/foo.py:42) → post as inline comments using the comments[] fields above. One --field pair per comment attribute.\n- All other content (blast radius, security verdict, test coverage, looks-good) → goes in the top-level body field.\n- Bundle ALL inline comments into one API call (one review object). Do not make separate API calls per finding.\n- Use the actual file path and line number from the diff. Verify the line exists in the diff before including it.\n- Do not truncate any finding.")}}'
