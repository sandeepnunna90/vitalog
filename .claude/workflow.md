# Per-story workflow (every story, no exceptions)

1. **Plan first.** Enter plan mode → write plan to `.claude/tasks/<STORY>.md` → wait for explicit approval before writing any code.

2. **Sync main.** Before branching, ensure local main is current:
   ```
   git checkout main && git pull --rebase origin main
   ```

3. **Create a feature branch.**
   ```
   git checkout -b feat/<story-id>-<short-slug>
   ```
   Example: `feat/b3-layer3`. All commits go to the branch — never directly to `main`.

4. **Implement** on the branch. Update the plan file as work progresses.

5. **Commit.** The pre-commit hook auto-runs `ruff check`, `ruff format --check`, and `mypy` — commit is blocked if any fail. Fix before committing, never skip hooks.

6. **Open PR.**
   ```
   gh pr create
   ```
   CI runs the test suite automatically. The post-PR hook invokes the `pr-review-expert` skill and posts the full review as a GitHub PR comment.

7. **Address review findings** in new commits on the same branch. Never amend published commits.

8. **User reviews and merges** after all checks pass.

# Definition of done (every story, no exceptions)

After the PR is merged, commit these three updates to `main` (or include them on the branch before merge):

| Artifact | What to update |
|---|---|
| `CLAUDE.md` | Move built files from "Up next" → "Built (Epic …)"; add any new gotchas |
| `.claude/tasks/README.md` | Flip story Status from ⬜ to ✅ |
| `.claude/tasks/<STORY>.md` | Append `### Implementation (date)` changelog: files created/modified, key design decisions, PR review fixes |

Do not close a story until all three are committed and pushed.
