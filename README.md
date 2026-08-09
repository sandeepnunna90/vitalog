# Vitalog

**A patient-facing health intelligence tool for people managing chronic conditions.**

Patients with chronic conditions see multiple specialists across multiple health systems, and their records end up scattered across portals, paper printouts, and memory. Vitalog gives them one place to upload lab reports, understand what changed over time, and walk into an appointment with a summary a doctor can actually use.

Upload a lab report in any format → Vitalog extracts and normalizes the biomarkers, tracks them longitudinally, surfaces condition-aware observations, answers natural-language questions about the history, and generates a one-page appointment summary where every claim is traceable to a source document.

Built MCP-first: the demo channel is Claude Desktop talking to a deployed MCP server. Python 3.11+, Claude via the Anthropic SDK, Supabase for persistence.

## How it works

```
Upload → Classify → OCR → Structure → Normalize → Persist
                                                      ↓
                        Trends · Observations · NLQ · Context cards
                                                      ↓
                                   Summary → Annotate → Export
```

| Stage | What happens |
|---|---|
| **Ingestion** | Upload validation, three-way document classification, OCR via AWS Textract with a Claude vision fallback, LLM structuring into typed Pydantic models, composite confidence scoring |
| **Normalization** | Alias lookup against a canonical biomarker taxonomy, UCUM unit conversion, reference-range validation, duplicate detection, and a pending queue for unrecognized biomarkers |
| **Intelligence** | Trend engine, observation generator, natural-language query handler with retrieval resolution, condition context cards, and a specialist summary generator |
| **Export** | Annotated summaries out to PDF, Markdown, or JSON |

Two cross-cutting pieces are worth calling out:

**AI Gateway.** Every LLM call in the system routes through a single chokepoint. Nothing instantiates the Anthropic client directly. That gateway owns layered guardrails, the versioned prompt registry, eval logging, and citation verification — which means prompt changes, model swaps, and safety rules all happen in one place instead of scattered across feature code.

**Citation verification.** Generated clinical text is only useful if you can check it. Summaries use structured tool-use to force the model to name its sources; observations and query answers are verified by parsing claims back against the retrieved records. Unverifiable claims don't ship to the patient.

Confidence is a three-band model rather than a single pass/fail threshold: high-confidence extractions auto-accept, a middle band routes to human review, and low-confidence extractions are rejected outright. Retention is classification-gated — recognized medical documents are kept, unsupported files are discarded after classification with only audit metadata retained.

## Validation

Extraction is checked against synthetic lab reports generated from vendor-style templates, each paired with ground truth so output can be compared field by field — decimal tolerance on values, fuzzy matching on biomarker names. This is a work in progress rather than a finished benchmark; the generators and comparison tooling live in `src/eval/`.

## Stack

| | |
|---|---|
| Language | Python 3.11+, Pydantic v2 (strict) for all LLM I/O schemas |
| Models | Claude via the Anthropic Python SDK — single provider by design |
| Interface | MCP server (FastMCP, six tools) over SSE, deployed on Render; CLI fallback |
| OCR | AWS Textract primary, Claude vision fallback |
| Persistence | Supabase (Postgres + Storage) behind a repository pattern |
| Auth | MCP OAuth 2.0 with dynamic client registration, Google sign-in via Supabase, per-request patient scoping |
| Quality | `ruff`, `mypy --strict`, `pytest` |

## Getting started

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), an Anthropic API key, a Supabase project, and AWS credentials for Textract.

```bash
git clone https://github.com/sandeepnunna90/vitalog.git
cd vitalog
make setup                  # uv sync + install git hooks
cp .env.example .env        # then fill in your keys
make migrate SUPABASE_DB_URL="<your connection string>"
```

Verify the install:

```bash
make test        # unit tests (integration tests skipped)
make lint        # ruff check + format check
make typecheck   # mypy --strict
```

Run the MCP server and point Claude Desktop at it:

```bash
uv run python scripts/run_mcp_server.py
```

## Documentation

Design docs live in `docs/` and are the source of truth for anything architectural:

- `docs/Vitalog_PRD_v2.md` — product spec
- `docs/Vitalog_architecture.md` — stack, architecture decision records, scope, known limitations
- `docs/vitalog_roadmap.md` — implementation sequencing

## Status and scope

Capstone project for the 100x Gen AI course, built solo. Ingestion, normalization, all six intelligence features, export, orchestration, and the MCP server are implemented.

Still in progress: validation coverage. Deliberately out of scope for this phase: the web UI (MCP-only for now), FHIR and provider-portal integrations, multi-patient support beyond the demo profile, and broad specialist coverage. The biomarker taxonomy ships as a 30-biomarker seed with a pending queue for anything outside it.

**Not a medical device.** Vitalog organizes and summarizes documents a patient already has. It does not diagnose, and it is not a substitute for a clinician.
