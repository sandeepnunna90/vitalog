# Task 16 — Demo rehearsal + recording

## Context

Final day. The capstone is judged on a single end-to-end demo: upload 3 lab documents → view HbA1c trend → generate cardiology summary → export PDF. This task does the rehearsal, the recording, and the final writeup. Roadmap §4 exit criteria 1, 2, 4, 5, 6, 8, 9 are verified here.

## Dependencies

- Every prior task. Specifically:
  - Tasks 04–09 for the upload-to-store flow
  - Task 11 for the trend
  - Task 13 for the summary
  - Task 14 for the MCP surface
  - Task 15 for adversarial proof

## In scope

**Rehearsal:**

- Run the full demo at least 3 times end-to-end via Claude Desktop, against hero data.
- Time each run; target < 5 min per roadmap §4 exit criterion #1.
- Note any rough edges (latency spikes, error messages, formatting issues) and patch them.

**Planted-hallucination demo:**

- Seed a deliberately-bad citation into a fixture summary path (e.g., wrong `source_record_id`).
- Show Mode A reject the doctored summary live — this is exit criterion #6 ("citation verifier catches at least one real hallucination").

**Recording:**

- Screen + audio capture of one clean run (QuickTime / OBS).
- Backup file stored locally; not committed to repo if large; reference in `README.md`.

**Writeup deliverables:**

- `EVAL_RESULTS.md`:
  - Extraction accuracy on eval corpus (per-document + aggregate)
  - Classification accuracy
  - Calibration report summary (from task 10)
  - Adversarial pass rate (from task 15)
  - Mode A / Mode B catch counts (real + planted)
  - Hero data details: 9 HbA1c points, 3 templates, span 2022–2026
- `RISKS.md` — pulled from `docs/vitalog_roadmap.md` §4 "Key risks" + architecture §12 + the capstone-specific list, condensed to one page.
- `FUTURE_WORK.md` — one-page pointer to `docs/vitalog_roadmap.md` v1 / v1.5 / v2 sections; specifically calls out the highest-priority deferred items (LLM-as-judge, LOINC Tiers 2/3, web UI, BAAs).
- Polish `README.md`: demo flow walkthrough, quickstart, env setup, recording link, status badge.

## Out of scope (deferred)

- Marketing collateral (post-capstone).
- Multi-version recordings (one clean demo is enough).
- Live deployment / public access (capstone is local).

## Files to create

- `EVAL_RESULTS.md`
- `RISKS.md`
- `FUTURE_WORK.md`
- Updates to `README.md`
- Demo recording (local file, path noted in `README.md`)

## Architecture references

- `docs/vitalog_roadmap.md` §4 exit criteria
- `docs/Vitalog_architecture.md` §12 — limitations and deferred items
- `docs/Vitalog_PRD_v2.md` §GTM Week 3 "Demo Slice"

## Step-by-step

1. Day 10 morning: full pipeline regression. `make test && make lint && make typecheck && make adversarial` all green.
2. Run the demo via Claude Desktop. Note rough edges. Patch.
3. Run again. Patch.
4. Run again. Should be < 5 min, clean.
5. Set up the planted-hallucination scenario; rehearse showing Mode A rejection.
6. Record the clean run + the planted-hallucination demo.
7. Write `EVAL_RESULTS.md`, `RISKS.md`, `FUTURE_WORK.md`.
8. Polish `README.md`; add recording reference.
9. Final commit, push if repo is on GitHub.

## Acceptance criteria

- [ ] Three clean demo runs back-to-back; each < 5 min.
- [ ] Hero longitudinal flow renders correctly (9-pt HbA1c, 3 visually distinct labs).
- [ ] Zero clinical recommendations across all summary + observation runs in eval.
- [ ] 20+ adversarial prompts all refuse.
- [ ] Mode A catches the planted hallucination on camera.
- [ ] `EVAL_RESULTS.md`, `RISKS.md`, `FUTURE_WORK.md` all written.
- [ ] Recording exists, location noted in `README.md`.
- [ ] Roadmap §4 exit criteria #1, #2, #3, #4, #5, #6, #7, #8, #9 all ticked.

## Verification

- Watch the recording end-to-end; confirm no errors, no clinical recommendations, citation rejection visible.
- `wc -l EVAL_RESULTS.md` ≥ 80 lines.
- `git log --oneline` shows the final polish commits.
- Repo `README.md` reads cleanly to someone who has never seen the project.
