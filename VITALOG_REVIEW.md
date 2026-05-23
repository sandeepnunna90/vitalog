# Vitalog — Codebase & Product Review

*Source: docs/, .claude/tasks/, src/, eval_corpus/, runs/. Compiled 2026-05-22 against branch `main` (commit `3a5b990`).*

---

## 1. What problem does Vitalog solve?

**The fragmented medical-records problem for chronic-condition patients.**

Per `docs/Vitalog_PRD_v2.md`:
> "Americans managing chronic conditions see multiple specialists across multiple health systems, but their health data remains scattered across portals, paper reports, and memory."

The persona is **"Mark" — a 56-year-old managing Type 2 Diabetes, Hypertension, and a borderline thyroid condition.** He sees multiple specialists, accumulates lab reports across labs (Quest, LabCorp, hospital labs), and walks into appointments without a coherent view of his history. The PRD frames this as the "11-minute summary problem" — patients arriving at appointments unprepared.

Vitalog's stated business objectives (PRD §Business Objectives):
- Give chronic-condition patients a unified, intelligent view of their own data
- Eliminate the "11-minute summary problem"
- Reduce redundant lab tests
- Empower higher-quality patient–doctor conversations

**Hard constraint baked into the architecture (architecture §3, principle P1):** "Patient safety over feature velocity." Zero clinical recommendations are allowed anywhere in the product. Vitalog is **explicitly not** a clinical decision support tool, not an EHR, not a telemedicine platform, and not a HIPAA covered entity. It is a tool that gives the patient (the data controller) leverage over their own data.

---

## 2. What is the solution? How does it work end-to-end?

Vitalog is an **MCP-first patient-facing health intelligence tool**. The capstone demo channel is **Claude Desktop via Model Context Protocol**; a web UI is explicitly deferred to v1 (ADR-08).

### Architecture (architecture §4)
A two-layer model with a four-concern value layer:
- **Top Layer (Interface):** MCP server today; web/WhatsApp deferred
- **Orchestration Layer:** thin workflow coordinator, no business logic
- **Value Layer:** four concerns
  - **Ingestion** — upload, classify, OCR, structure
  - **Normalization** — LOINC-aware canonical naming, UCUM unit conversion, dedup, provenance
  - **Intelligence** — trends, NLQ, observations, summaries
  - **Persistence** — Postgres + Storage via repository pattern
- **AI Gateway (cross-cutting):** single chokepoint for every LLM call, owning prompt versioning, model routing, and layered guardrails

### End-to-end happy path (architecture §8.1)
1. Mark uploads a lab PDF via Claude Desktop (MCP tool `upload_document`)
2. **Ingestion: validate** MIME/size; **probe** for empty/corrupt
3. **Classify** (LLM via Gateway): `lab_report` / `recognized_unsupported` / `not_supported`
4. **Classification-gated storage** (architecture §7.6): `lab_report` + `recognized_unsupported` retained permanently; `not_supported` **discarded** with audit metadata only
5. **AWS Textract** extracts text + tables
6. If Textract confidence below threshold → **Claude vision-LLM fallback**
7. **Structurer** (Claude Sonnet via Gateway) → biomarker candidates with field-level confidence
8. **Composite confidence** = `min(textract, llm, classification)` → **three-band routing**: auto-accept (≥95), review (70–94), reject (<70)
9. **Normalization:** Tier 1 alias lookup → unit conversion to canonical UCUM → physiological range check → duplicate detection → Tier 4 pending-taxonomy queue for unmatched names
10. **Persistence:** records stored with full provenance (`original_*` + `canonical_*` + `verified_by` ∈ {auto, user, admin, pending_user})
11. Mark queries trends, asks natural-language questions, generates a one-page appointment summary with citation-verified numerics, and exports as PDF/markdown/JSON

### Two citation-verification modes (architecture §7.2.1)
- **Mode A (structured tool-use)** — Summary Generator. Every numeric value emits a citation object `{value, unit, collection_date, source_record_id}`. Deterministic lookup against the retrieval set; unverifiable citation causes **atomic rejection** of the entire generation.
- **Mode B (parse-and-match)** — Observation Generator + NLQ Handler. Numeric tokens in prose are extracted and matched against the retrieval set with ±0.5% decimal tolerance / exact-match integers / unit-consistency check; unmatched numerics cause rejection.

The two-mode design is intentional: structured-only would produce robotic NLQ responses; parse-only would weaken verification on summaries.

---

## 3. What features have been built?

Per `.claude/tasks/README.md`, the capstone backlog is **33 stories across 8 epics totalling 144 points**. **30 of 33 stories are marked done (✅)**. Three outstanding stories:
- **C5 — Confidence band calibration** (6 pts, ⬜ pending)
- **H1 — Hero longitudinal dataset (HbA1c × 9 × 3 labs)** (3 pts, ⬜ pending)
- **H2 — Demo polish + rehearsal** (5 pts, ⬜ pending)

### Epic-by-epic status

| Epic | Stories shipped | Notes |
|---|---|---|
| **A — Foundation** | A1, A2, A3 ✅ | Repo scaffolding, reference-data seed, Supabase persistence layer with repository pattern |
| **B — AI Gateway + Guardrails** | B1–B5 ✅ | Gateway core, L1+L2, L3 deterministic validators, Mode A verifier, Mode B verifier |
| **C — Eval Corpus & Harness** | C1, C2, C3, C4 ✅; **C5 ⬜** | Synthetic generator; corpus of 13 docs (10 synthetic + 3 adversarial); accuracy harness; adversarial prompt suite. C5 confidence band calibration not yet run. |
| **D — Ingestion** | D1–D6 ✅ | Upload + probes, three-category classifier, classification-gated storage, Textract primary path, vision-LLM fallback, structurer + composite confidence + 3-band routing |
| **E — Normalization** | E1–E4 ✅ | Tier 1 alias lookup, Tier 4 pending queue + admin CLI, unit conversion + range validation, duplicate detection |
| **F — Intelligence** | F1–F6 ✅ | Trend Engine, Observation Generator (Mode B), NLQ Handler, Context Cards, Summary Generator (Mode A), Annotation + Export (PDF/MD/JSON) |
| **G — Top Layer** | G1, G2, G3 ✅ | MCP server with 6 tools wired; Mark's hardcoded patient profile; configurable patient ID via env var |
| **H — Demo** | H3, H4, H5 ✅; **H1, H2 ⬜** | H3 multi-source upload (URL, file path, base64); H4 Render deployment via SSE + Docker; H5 MCP OAuth 2.0 + per-request `patient_id` via contextvar |

### The 6 MCP tools (the demo surface)

| Tool | What it does |
|---|---|
| `upload_document` | Upload a lab PDF via URL, file path, or base64 |
| `list_biomarkers` | Latest value per canonical biomarker |
| `get_trend` | Longitudinal trend + guideline target bands |
| `query_records` | Natural-language query with Mode B verification |
| `prepare_summary` | Mode A citation-verified one-page appointment summary |
| `export_summary` | PDF (base64) / markdown / JSON export |

---

## 4. Technical stack and AI/ML components

### Stack

| Layer | Choice |
|---|---|
| Language / runtime | Python 3.11+ |
| Package manager | uv (Astral) |
| LLM SDK | Anthropic Python SDK — single-provider |
| Primary model | Claude Sonnet (latest) |
| Vision fallback | Claude with vision |
| OCR (primary) | AWS Textract |
| Schema validation | Pydantic v2, `ConfigDict(strict=True)` |
| Database | Supabase Postgres |
| Object storage | Supabase Storage |
| MCP framework | FastMCP |
| MCP transport | SSE (Render) / stdio (local) |
| Tooling | ruff, mypy --strict, pytest, native git pre-commit hook |
| Deployment | Render (render.yaml + Docker) |
| Auth | Supabase Google OAuth + custom MCP OAuth 2.0 (RFC 7591 dynamic client registration) |
| PDF reading | PyMuPDF (fitz) |
| String similarity | rapidfuzz (extraction-accuracy comparator) |

### AI / LLM components

1. **Document classifier** (`prompts/classification/v1.md`) — three-category classification
2. **Structurer** (`prompts/structurer/v1.md`) — converts Textract output to biomarker candidates with field-level confidence
3. **Vision-LLM fallback** — Claude vision when Textract confidence is low
4. **Observation Generator** (`prompts/observation/v1.md`) — 1–3 sentence factual statements per biomarker; Mode B verified
5. **NLQ Handler** (`prompts/nlq/v1.md`) — natural-language queries; retrieval-first, Mode B verified
6. **Summary Generator** (`prompts/summary/v4.md`) — structured one-page appointment summary; Mode A citation-verified

### Safety / guardrails (four layers)

- **Layer 1** — input PII redaction for logs + injection-pattern detection (recurses into nested dicts)
- **Layer 2** — safety preamble + few-shot refusals (medical_advice, medication_adjustment, diagnosis) + schema enforcement
- **Layer 3 deterministic** — banned-phrase regex + Pydantic schema validator
- **Mode A citation verifier** — 4 checks: lookup, ownership, retrieval-set scope, field-match (±0.5%)
- **Mode B citation verifier** — numeric extraction + match with unit-consistency gate
- **Adversarial prompt suite** — 20+ examples targeting clinical-advice elicitation
- **LLM-as-judge** — **explicitly NOT built** (architecture §12: "the most significant unmitigated risk in the capstone safety posture")

---

## 5. Demo flow — what can actually be demonstrated today

### What works end-to-end (confirmed per H5 implementation notes, 2026-05-22)
- Claude Desktop connects via `mcp-remote` to `https://vitalog-9z6b.onrender.com/sse`
- First connection opens browser for Google OAuth login
- Lab reports uploaded via Google Drive URLs; biomarkers extracted and stored
- Trend queries, NLQ handler, and summary generator confirmed working
- Out-of-scope queries (medications, diet, appointments) return a safe refusal **without calling the LLM**

### Hero demo sequence
1. Claude Desktop → OAuth login → `upload_document` for a lab PDF
2. `list_biomarkers` to see what was extracted
3. `get_trend("hba1c")` to see longitudinal data with ADA target band overlay
4. `query_records("show me my diabetes markers")` → grouped biomarker response
5. `prepare_summary()` → Mode A citation-verified one-page summary
6. `export_summary(summary_id, "pdf")` → base64 PDF returned

### What is NOT yet ready for the demo
- **H1 — Hero longitudinal dataset** (HbA1c × 9 data points × 3 labs over 4 years) is not yet generated. The PRD success criterion — "Mark can view a longitudinal trend for HbA1c across 9 data points from 3 different labs on one chart" — cannot currently be demonstrated.
- **H2 — Demo polish + rehearsal** is pending.
- **C5 — Confidence band calibration** has not been run.

---

## 6. The build journey (what was built and when)

**Backlog scope:** 3-week capstone, ~10-day suggested loading, 33 stories, 144 points.

### Suggested 10-day loading from the README

| Day | Stories | Points |
|---|---|---|
| 1 | A1, A2, A3 | 13 |
| 2 | B1, B2, C1 | 13 |
| 3 | B3, D1, D2 | 11 |
| 4 | D3, D4, C2 | 11 |
| 5 | D5, D6 | 11 |
| 6 | E1, E2, E3, E4 | 14 |
| 7 | B4, B5, C3, C5 | 19 |
| 8 | F1, F2, F3, F4, G2 | 19 |
| 9 | F5, F6, G1 | 22 |
| 10 | C4, H1, H2 | 11 |

Days 7 and 9 were the heaviest. The planned relief valve (cutting F4 context cards and F6's markdown/JSON formats) was never needed — both shipped.

### Key design decisions and pivots during the build
- **biomarker_groups.json replaced an earlier `condition_biomarker_map.json`** — simpler flat list structure
- **Summary prompt iterated four times** (`summary/v1.md` → `v4.md`) — strict versioning preserved
- **F2 Observation Generator** needed several guards: pending-taxonomy guard, synthetic guideline-bound records in retrieval set, month-first date formatting
- **F3 NLQ** required token stripping (non-alphanumeric) and ≥8-char significant-word threshold to avoid false positives on "type", "chronic", etc.
- **F5 Summary citations** use `str` types, not `date`/`UUID` — Pydantic strict=True would reject LLM JSON output otherwise
- **H4 Render deployment** added; H5 added MCP OAuth 2.0 with RFC 7591 after PR review found open-redirect vulnerability
- **47 issues** found in a prior codebase review (5 critical / 10 high / 16 medium / 16 low) — all addressed

### Timeline anchors from git
- Latest eval run: `20260518T132958Z` (2026-05-18)
- H5 (auth + Render) merged: 2026-05-22 (today)
  - `3a5b990` Merge PR #39 (feat/h5-user-auth)
  - `831d708` fix(auth): RFC 7591 dynamic client registration + load_dotenv
  - `23b6f66` fix(review): open redirect, auth tests, migration file

---

## 7. Measurable outcomes from the codebase

### Extraction accuracy (eval_corpus/runs/20260518T132958Z/accuracy.md)

| Metric | Value |
|---|---|
| Total documents | 13 (10 synthetic + 3 adversarial) |
| Overall F1 (all fields) | **1.000** |
| TP / FP / FN | 192 / 0 / 0 |
| Adversarial split | 32/32 perfect |
| Synthetic split | 160/160 perfect |
| Classification accuracy | 13/13 |

**Important caveat:** `scripts/run_accuracy.py --dry-run` produces "~100% F1 via GT self-comparison, no API calls." The perfectly clean 1.000 numbers strongly suggest this is a dry-run report, not a live extraction run. Live-extraction accuracy numbers are not present in the repo.

### Cost data (from runs/cost_notes.md)
- AWS Textract free tier: 1,000 pages/month for first 3 months
- Capstone usage: well under 100 pages, free-tier-covered
- Production projection at 10K uploads/month × 2 pages: ~$600/month Textract
- Per-document upload LLM cost: ~$0.01–0.05
- Per-summary LLM cost: ~$0.02–0.08

### Reference data scope
- `biomarker_taxonomy.json`: **84 entries** (docs say "~30 seed" — actual count is materially larger; docs appear stale)
- `biomarker_groups.json`: **9 conditions** with embedded guideline citations

### AI Gateway worst-case fan-out
- Single Summary call: 3 (network retries) × 2 (schema retry) × 2 (L3 retry) = **12 Anthropic calls**

---

## 8. Discrepancies and gaps flagged

1. **Taxonomy size mismatch** — CLAUDE.md says "~30-biomarker seed" but `biomarker_taxonomy.json` contains **84 entries**. Docs are stale.
2. **Eval corpus size** — architecture targets "~18 documents" (ADR-07, PRD §Testing). Actual corpus is **13 documents**; `redacted_real/` is empty. The 3–5 redacted real reports committed to are not present.
3. **accuracy.md is likely a dry-run** — 1.000 F1 across 192 fields with 0 FP/FN is consistent with `--dry-run` (GT self-comparison). No live-extraction run numbers are in the repo.
4. **H1 hero data not built** — "HbA1c × 9 × 3 labs" demo success criterion has no data behind it yet.
5. **C5 calibration not run** — `THRESHOLD_AUTO_ACCEPT = 95`, `THRESHOLD_REJECT = 70` remain initial placeholder values.
6. **LLM-as-judge not built** — architecture §12 calls it "the most significant unmitigated risk." Subtle qualitative claims ("trending up", "concerning pattern") can pass all built guardrails.

---

## What the codebase most strongly supports in a pitch

1. **Patient-safety-first design** — every architectural decision traces to P1 ("patient safety over feature velocity"); zero clinical recommendations anywhere
2. **Two-mode citation verification** — Mode A (structured) for summaries, Mode B (parse-and-match) for NLQ/observations — specifically designed to catch hallucinated biomarker values
3. **End-to-end MCP product** on Render with real OAuth 2.0 (RFC 7591 dynamic client registration) — not a notebook demo
4. **Eval-driven development** — real harness with adversarial regression suite
5. **Honest scope discipline** — 18 known limitations enumerated in architecture §12; nothing hidden

## Before the demo: two critical things to do

1. **Build H1 (hero longitudinal dataset)** — generate HbA1c × 9 data points × 3 labs. Without this, the headline demo story has no data.
2. **Clarify which accuracy number to quote** — either run the harness in live mode and report that number, or don't quote F1 at all. Quoting 1.000 F1 from a dry-run would be misleading.
