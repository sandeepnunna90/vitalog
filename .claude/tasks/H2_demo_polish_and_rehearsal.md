# H2 — Demo polish + rehearsal

**Epic:** Demo
**Points:** 5
**Priority:** Critical
**Depends on:** All
**Architecture refs:** roadmap §4 (Exit criteria); PRD v2 GTM week 3 + Demo Slice

## User story

As the founder approaching capstone submission,
I want a final pass that resolves the pending taxonomy queue, runs the adversarial regression, runs the accuracy harness, executes the full demo flow end-to-end on a clean environment, and produces a recorded backup video + README + AGENTS.md,
So that the demo is bulletproof and capstone reviewers have everything they need.

## Why this matters

Roadmap §4 Exit criteria list every one of these items as a hard gate. This story is the consolidation pass that makes "complete" actually mean "complete" — not "complete except for the queue, the recording, and the README".

## Acceptance criteria

1. **Given** the pending taxonomy queue, **When** `python scripts/resolve_pending.py list` runs, **Then** the output is "0 pending entries" (per architecture §12 OQ5 and PRD v2 Success Criteria).
2. **Given** the adversarial suite, **When** `python scripts/run_adversarial.py` runs, **Then** all 20+ prompts pass (refusal or safe_redirect), exit code is 0.
3. **Given** the accuracy harness, **When** `python scripts/run_accuracy.py --corpus eval_corpus/` runs, **Then** synthetic accuracy ≥95%, redacted_real accuracy ≥85%, adversarial classification is correct on all 3.
4. **Given** the citation verifier, **When** the founder forces a known-hallucinated value into the eval pipeline once during testing, **Then** Mode A rejects it (proof of working defense — roadmap §4 exit criterion 6).
5. **Given** a clean environment (fresh `uv sync` + Supabase project + Claude Desktop config), **When** the founder runs the demo flow end-to-end from clone to PDF export, **Then** the entire flow completes in under 5 minutes (roadmap §4 exit criterion 1).
6. **Given** the rehearsal, **When** the demo is recorded as backup video, **Then** the recording is committed to `demo/` directory and linked from the README.
7. **Given** README + AGENTS.md, **When** a stranger reads them, **Then** they can: clone, install, run, and execute the hero scenario without any other guidance.
8. **Given** the writeup deliverables, **When** the founder submits the capstone, **Then** PRD, architecture doc, roadmap doc, eval results report (`eval_corpus/calibration_report.md` + `eval_corpus/runs/<latest>/accuracy.md`), risk register, and this README are all present and consistent.

## Files to create / modify

- `scripts/demo_dry_run.sh` — orchestrates the full pre-demo check sequence
- `README.md` — final pass: clone → run → demo instructions
- `AGENTS.md` — guidance for future Claude Code work on the repo (mirrors project CLAUDE.md style)
- `demo/demo_script.md` — exact words / steps for the live demo (in case live nerves)
- `demo/recording.mp4` (or `.mov`) — backup video, committed via Git LFS or linked from README
- `eval_corpus/runs/final/` — final accuracy + adversarial results, committed
- `Makefile` — `pre-demo-check` target now runs the full sequence end-to-end

## Implementation notes

- `pre-demo-check` runs (in order): queue check (E2) → adversarial suite (C4) → accuracy harness (C3) → end-to-end smoke (a scripted invocation of the MCP upload → trend → summary → export flow). Each step exits non-zero on failure.
- The "forced hallucination" test (AC #4) is a one-time exercise — author a synthetic test that prompts the Summary Generator with retrieval data missing one of the records the prompt is expected to cite, observe Mode A rejection, log the result in `demo/citation_defense_proof.md`. Roadmap §4 exit criterion 6 requires this evidence.
- The demo recording is a one-take video of the hero scenario, captured via screen recording with audio narration. Keep it under 5 minutes (matches roadmap §4 exit criterion 1).
- README structure: project summary (one paragraph) → setup (`uv sync` + `.env` + Supabase + Claude Desktop config) → demo (run `make demo` for the scripted hero flow) → docs (links to PRD v2 / architecture / roadmap) → repo layout.
- AGENTS.md tells future Claude Code agents the workflow rules (plan mode, `.claude/tasks/` pattern, citation discipline, prompt versioning Gotcha). It's the in-repo distillation of the project CLAUDE.md.
- Capstone submission cross-check: PRD v2 GTM week 3 → all items present; PRD v2 Success Criteria → all 6 verified; roadmap §4 exit criteria → all 9 items checked.

## Verification

- `make pre-demo-check` exits 0
- Cold-machine test: clone the repo to a different machine (or fresh VM), run setup, run the demo — works first-try
- Manual: capstone reviewers can reproduce the demo from the README alone

## INVEST check

- [x] Independent — all other stories required
- [x] Negotiable — exact rehearsal cadence flexible
- [x] Valuable — gates the actual submission
- [x] Estimable — well-bounded consolidation
- [x] Small — 5 pts (mostly orchestration + writeup)
- [x] Testable — `pre-demo-check` is the test

## Deferred (explicitly out of this story)

- Public-facing landing page — v1
- Provider-facing demo materials — v2
- Marketing assets — v1
- Live demo to investors — post-capstone

## Notes / changelog

### Cohort demo 2026-05-22

**Scope adjustment:** Original AC set was written for capstone submission (cold-machine test, AGENTS.md, recording committed to git, etc.). Today's goal is a clean cohort demo — not the full submission checklist.

**Actual demo script:** `docs/demo_queries.md` — execute in order, live, via Claude Desktop connected to `https://vitalog-9z6b.onrender.com/sse`.

**Demo flow (from demo_queries.md):**
1. Upload lab report #1 via Google Drive URL
2. Upload lab report #2 via Google Drive URL
3. `List all my biomarkers`
4. Trend queries: HbA1c, glucose, LDL, HDL, triglycerides, creatinine, hemoglobin
5. NLQ queries: cholesterol history, kidney function, cardiovascular risk, red blood cell status, thyroid health
6. `Generate a health summary for me` → Mode A citation-verified output
7. `Export the summary as a PDF` (or markdown)
8. Guardrail queries: diet advice, medications, appointments, calorie tracking, family member comparison, blood pressure

**Deferred for today (not blocking demo):**
- H1 hero longitudinal dataset — not needed for cohort
- `scripts/demo_dry_run.sh` / `make pre-demo-check`
- AGENTS.md
- Backup video recording
- Cold-machine reproduction test
- C5 confidence band calibration

**What was verified before demo:**
- MCP OAuth flow confirmed working (H5)
- Two lab reports uploaded and biomarkers extracted (H5 test run)
- Trend, NLQ, summary, export, and guardrail paths all confirmed live
