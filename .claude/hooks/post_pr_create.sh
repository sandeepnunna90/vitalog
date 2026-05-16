#!/usr/bin/env bash
# PostToolUse (Bash) — fires after every Bash tool call.
# Handles two events:
#   1. gh pr create  → trigger automated PR review via pr-review-expert skill
#   2. git push      → resolve review threads whose findings are fixed in the pushed commits
set -euo pipefail

input=$(cat)
cmd=$(echo "$input" | jq -r '.tool_input.command // ""')

# ── 1. gh pr create — trigger automated review ────────────────────────────────
if echo "$cmd" | grep -q 'gh pr create'; then
  pr_url=$(echo "$input" | jq -r '.tool_response.stdout // ""' \
    | grep -oE 'https://github\.com/[^/]+/[^/]+/pull/[0-9]+' \
    | head -1)
  pr_num=$(echo "$pr_url" | grep -oE '[0-9]+$')
  repo_path=$(echo "$pr_url" | grep -oE 'github\.com/[^/]+/[^/]+' | sed 's|github\.com/||')

  if [ -z "$pr_num" ]; then
    exit 0
  fi

  jq -n --arg num "$pr_num" --arg url "$pr_url" --arg repo "$repo_path" \
    '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":("PR #" + $num + " was just opened (" + $url + "). Immediately invoke the pr-review-expert skill to review it. When the review is complete, post it as a single GitHub review using the API — do NOT use gh pr review --comment. Use this command structure:\n\ngh api repos/" + $repo + "/pulls/" + $num + "/reviews --method POST \\\n  --field event=COMMENT \\\n  --field body='"'"'<overall summary: blast radius, security verdict, test coverage delta, looks-good items>'"'"' \\\n  --field '"'"'comments[][path]=src/foo.py'"'"' --field '"'"'comments[][line]=42'"'"' --field '"'"'comments[][body]=<finding text>'"'"'\n\nRules:\n- Findings that cite a specific file:line (e.g. src/foo.py:42) → post as inline comments using the comments[] fields above. One --field pair per comment attribute.\n- All other content (blast radius, security verdict, test coverage, looks-good) → goes in the top-level body field.\n- Bundle ALL inline comments into one API call (one review object). Do not make separate API calls per finding.\n- Use the actual file path and line number from the diff. Verify the line exists in the diff before including it.\n- Do not truncate any finding.")}}'
  exit 0
fi

# ── 2. git push — resolve fixed review threads ────────────────────────────────
if echo "$cmd" | grep -qE '^git push'; then
  branch=$(git branch --show-current 2>/dev/null || true)
  [ -z "$branch" ] && exit 0

  pr_json=$(gh pr list --head "$branch" --state open --json number,url 2>/dev/null || true)
  pr_num=$(echo "$pr_json" | jq -r '.[0].number // empty' 2>/dev/null || true)
  pr_url=$(echo "$pr_json" | jq -r '.[0].url // empty' 2>/dev/null || true)
  repo_path=$(echo "$pr_url" | grep -oE 'github\.com/[^/]+/[^/]+' | sed 's|github\.com/||' || true)

  [ -z "$pr_num" ] && exit 0

  jq -n --arg num "$pr_num" --arg url "$pr_url" --arg repo "$repo_path" \
    '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":("You just pushed to PR #" + $num + " (" + $url + "). Check for unresolved review threads and resolve any whose finding is addressed by the commits you just pushed.\n\nStep 1 — fetch unresolved threads:\ngh api graphql -f query='"'"'{ repository(owner: \"OWNER\", name: \"REPO\") { pullRequest(number: NUM) { reviewThreads(first: 20) { nodes { id isResolved comments(first: 1) { nodes { path body } } } } } } }'"'"'\n(replace OWNER/REPO/NUM from: " + $repo + " / " + $num + ")\n\nStep 2 — for each thread where isResolved=false, read the comment body and check whether the commits you just pushed fix that specific finding. Only resolve threads whose finding is genuinely addressed.\n\nStep 3 — resolve each addressed thread:\ngh api graphql -f query='"'"'mutation { resolveReviewThread(input: {threadId: \"<NODE_ID>\"}) { thread { isResolved } } }'"'"'\n\nDo NOT resolve threads for findings that are still open or only partially addressed.")}}'
  exit 0
fi

exit 0
