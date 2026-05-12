# Vitalog capstone task index

10-day implementation breakdown. Each task is one Claude Code session. Task files follow the standard template (Context, Dependencies, In scope, Out of scope, Files to create, Architecture references, Step-by-step, Acceptance criteria, Verification).

Authoritative scope contracts:

- [docs/Vitalog_PRD_v2.md](../../docs/Vitalog_PRD_v2.md)
- [docs/Vitalog_architecture.md](../../docs/Vitalog_architecture.md) §11 capstone scope
- [docs/vitalog_roadmap.md](../../docs/vitalog_roadmap.md) §4 capstone

## How to use this

1. Pick the next task by lowest unblocked number.
2. Open the task file in a fresh Claude Code session.
3. Each task file is self-contained — do not assume earlier context is in the new session.
4. Update the task file as work progresses; append change notes for handoff.
5. When done, mark the acceptance criteria checkboxes and move on.

## Must-ship tasks (17)

| # | File | Day | Hrs | Blocks |
|---|------|-----|-----|--------|
| 00 | [00-repo-bootstrap.md](00-repo-bootstrap.md) | 1 | 1–2 | Everything |
| 01 | [01-pydantic-schemas.md](01-pydantic-schemas.md) | 1 | 2 | 02, 04, 07, 08, 11, 13 |
| 02 | [02-ai-gateway-scaffold.md](02-ai-gateway-scaffold.md) | 1–2 | 2–3 | 04, 07, 12, 13 |
| 03 | [03-eval-corpus-and-hero-data.md](03-eval-corpus-and-hero-data.md) | 2 | 3 | 04, 07, 10, 15, 16 |
| 04 | [04-document-classifier.md](04-document-classifier.md) | 3 | 2 | 05, 07 |
| 05 | [05-textract-client.md](05-textract-client.md) | 3 | 2–3 | 06, 07 |
| 06 | [06-vision-llm-fallback.md](06-vision-llm-fallback.md) | 4 | 2 | 07 |
| 07 | [07-llm-structurer-confidence.md](07-llm-structurer-confidence.md) | 4 | 3 | 08, 09, 10 |
| 08 | [08-persistence-supabase-repos.md](08-persistence-supabase-repos.md) | 5 | 3 | 09, 11, 13, 14 |
| 09 | [09-normalization-tier1-ucum-pending.md](09-normalization-tier1-ucum-pending.md) | 5–6 | 3 | 10, 11, 13 |
| 10 | [10-confidence-band-calibration.md](10-confidence-band-calibration.md) | 6 | 2 | demo polish |
| 11 | [11-trend-engine.md](11-trend-engine.md) | 6 | 2 | 13, 14 |
| 12 | [12-observation-generator-mode-b.md](12-observation-generator-mode-b.md) | 7 | 2–3 | 14, 15 |
| 13 | [13-summary-generator-mode-a.md](13-summary-generator-mode-a.md) | 7–8 | 3–4 | 14, 15 |
| 14 | [14-mcp-server-six-tools.md](14-mcp-server-six-tools.md) | 8–9 | 3 | 16 |
| 15 | [15-adversarial-regression-suite.md](15-adversarial-regression-suite.md) | 9 | 2 | 16 |
| 16 | [16-demo-rehearsal-and-recording.md](16-demo-rehearsal-and-recording.md) | 10 | 2–3 | — |

## If-time tasks (2)

Slot in between tasks 09 and 14 only if Day 5 wraps ahead of schedule:

| # | File | Notes |
|---|------|-------|
| 17 | [17-nlq-handler-retrieval-mode-b.md](17-nlq-handler-retrieval-mode-b.md) | Enables Scenario 4 in demo |
| 18 | [18-patient-profile-onboarding.md](18-patient-profile-onboarding.md) | Replaces hardcoded Mark JSON |

## Dependency graph (read top-down)

```
00 ─┬─ 01 ─┬─ 02 ──┬─ 04 ─┐
    │      │       │       │
    │      │       ├─ 07 ──┼─ 08 ─┬─ 09 ─┬─ 10
    │      │       │       │      │       │
    │      │       │       │      │       └─ 11 ─┬─ 12 ─┐
    │      │       │       │      │              │       ├─ 14 ──┬─ 16
    │      │       │       │      │              └─ 13 ─┘       │
    │      │       │       │      └──────────────────────────┘   │
    │      │       │       └─ 05 ─┬─ 06                          │
    │      │       │              └──────────────────────────────┘
    │      │       └─ 03 ──────────────────────────────────── 15 ┘
    │      │
    │      └─ shared schemas used by 04, 07, 08, 11, 13
    │
    └─ folder structure + tooling used by all
```

## What's explicitly cut for 10 days

Documented in detail in [plan file](../../../../.claude/plans/vitalog-prd-md-vitalog-architecture-md-smooth-wave.md):

- NLQ Handler → if-time only (task 17)
- Patient onboarding flow → if-time only (task 18)
- Confidence band calibration → grid-search only, not full Appendix D methodology
- Observation Generator → 1 sentence per biomarker (not 1–3)

## Coverage check against roadmap §4

Every roadmap §4 in-scope bullet is owned by a task:

- **Ingestion** — Textract (05), vision fallback (06), classification (04), three-band model + composite confidence (07), week-2 calibration (10)
- **Normalization** — Tier 1 + Tier 4 + UCUM + duplicates + taxonomy seed (09)
- **Persistence** — Supabase repos + classification-gated storage + repository pattern (08)
- **Intelligence** — Trend Engine (11), Observation Generator (12), NLQ Handler (17 if-time), Summary Generator + cardiology (13), hero longitudinal data (03)
- **AI Gateway and guardrails** — Gateway scaffold + Layers 1–3 + eval logging (02, 12, 13)
- **Eval suite** — Corpus generator + ground truth + adversarial prompts (03, 15)
- **Top Layer** — MCP server with 6 tools (14)
- **Repo and tooling** — Bootstrap + synthetic generator + redaction process placeholder (00, 03)

## Roadmap §4 exit criteria → owning task

1. End-to-end demo < 5 min → task 16
2. Hero longitudinal flow → tasks 03 + 11 + 14
3. Extraction accuracy measured → tasks 03 + 07 + 16
4. Zero clinical recommendations → tasks 12 + 13 + 15
5. 20+ adversarial prompts return refusals → task 15
6. Citation verifier catches a real hallucination → tasks 13 + 15 + 16
7. Final writeup (PRD, arch, roadmap, eval results, risks, future work) → task 16
8. Demo recording → task 16
9. Clean repo + README → tasks 00 + 16
