# Vitalog — Product Requirements Document

**Version:** 2.0 — Architecture-Aligned Draft
**Author:** Solo Founder
**Date:** 2026-05-11
**Timeline:** 3 weeks to capstone submission
**Companion document:** [Vitalog_architecture.md](Vitalog_architecture.md) (authoritative for technical decisions)

---

## 🔄 Changes from v1

This version aligns the PRD with decisions made in `Vitalog_architecture.md` (v1.0, May 2026). Eleven misalignments were resolved:

1. **Interface scope.** Capstone is **MCP-only via Claude Desktop**; web UI deferred to v1 (architecture ADR-08).
2. **OCR strategy.** "OCR runs" specified as **AWS Textract primary + Claude vision fallback** (architecture ADR-02).
3. **Normalization concern added.** LOINC-aware canonical taxonomy + UCUM unit conversion + tiered resolution + pending taxonomy queue — all absent from v1 PRD (architecture §5.2, ADR-03).
4. **Confidence model.** Binary ≥90% threshold replaced with **three-band model (≥95 auto-accept / 70–94 review / <70 reject)**, calibrated week 2 (architecture §5.1.1, Appendix D).
5. **Storage policy.** v1 PRD's "never deleted" rule contradicted v2 architecture; replaced with **classification-gated retention** (architecture §7.6).
6. **Classification taxonomy.** Four-category list collapsed to three top-level categories with rich subtype captured for v1 (architecture §5.1).
7. **AI Gateway + layered guardrails.** Added as functional requirements — not just prompt-engineering directives (architecture §7.1, §7.2).
8. **Citation verification Modes A and B.** Made explicit as binding constraints on Summary, Observation, and NLQ outputs (architecture §7.2.1).
9. **Eval corpus.** "20+ real reports" replaced with **~18-document corpus combining templated synthesis + 3–5 redacted real reports** (architecture ADR-07).
10. **Specialist scope.** Demo commitment recast as "a specialist summary" to inherit architecture's 1–2 specialist scope without over-committing.
11. **Export formats.** "PDF / plain text / JSON" aligned to **PDF / markdown / JSON** to match the MCP `export_summary` tool (architecture §5.7).

---

## 📝 Abstract

Vitalog is a patient-facing health intelligence tool that solves the fragmented medical records crisis. Americans managing chronic conditions see multiple specialists across multiple health systems, but their health data remains scattered across portals, paper reports, and memory. Vitalog gives patients like Mark — a 56-year-old managing Type 2 Diabetes, Hypertension, and a borderline thyroid condition — a single place to upload, understand, and present their health history. The product ingests documents in any format, extracts and normalizes biomarker data, builds longitudinal trend views with condition-aware context, and generates a one-page appointment summary a doctor can actually use. **Built MCP-first for the capstone (Claude Desktop as the demo channel), with the web UI deferred to v1.** Designed to scale into a real business.

---

## 🎯 Business Objectives

- Give chronic condition patients a unified, intelligent view of their own health data for the first time
- Eliminate the "11-minute summary problem" — patients walking into appointments without their history
- Reduce redundant lab tests by making prior results visible and organized
- Empower patients to have higher-quality conversations with their doctors
- Demonstrate a viable AI-powered health intelligence product at capstone demo
- Establish foundational architecture that can scale to FHIR integrations and provider-facing features post-launch

---

## 📊 KPI

| GOAL | METRIC | QUESTION |
|------|--------|----------|
| Core flow completion | % of users who upload → view trend → generate summary | Does the product deliver end-to-end value in one session? |
| Extraction accuracy | % of biomarker fields correctly extracted per document | Is the parser reliable enough to trust? |
| Summary usefulness | % of generated summaries exported or shared by user | Do patients find the summary worth taking to an appointment? |
| Time to value | Minutes from first upload to first trend view | How fast does Mark see the product working? |

---

## 🏆 Success Criteria

**Capstone (3 weeks):**
- Mark can upload any lab document (PDF or photo) and see structured biomarker data within a reasonable session (latency targets are inputs to week-3 measurement, not preconditions)
- Mark can view a longitudinal trend for HbA1c across 9 data points from 3 different labs — on one chart
- Mark can generate a one-page **specialist** appointment summary, add a personal note, and export it as PDF or markdown
- Zero clinical recommendations appear anywhere in the product — only facts, published ranges, and observations
- End-to-end demo flow runs cleanly: upload → parse → normalize → trend → appointment summary
- **Pending taxonomy queue is resolved before demo time** (admin queue empty at demo) — per architecture §12 open question 5

**Business (post-launch):**
- Mark walks out of every appointment understanding his full health trend
- Vitalog becomes the tool patients open before every appointment, not just once

---

## 🚶‍♀️ User Journeys

**Mark's Primary Journey — First Use:**
Mark downloads his latest HbA1c result from the Quest portal. He uploads it to Vitalog **via Claude Desktop**. Within seconds, he sees a structured card: test name, value, reference range, date, lab source. He navigates to the HbA1c trend view and sees — for the first time — all nine results from the last four years plotted on a single timeline with the ADA target line. He types "show me my diabetes markers" and sees HbA1c and fasting glucose grouped together with context cards explaining what each one means. He has a cardiology appointment on Friday. He selects "Prepare for appointment," chooses Cardiologist / First Visit, reviews the generated summary, adds a note about his recent statin start, and exports a PDF. He emails it to the cardiologist's office the night before. He walks in prepared.

**Mark's Recurring Journey — Follow-Up Visit:**
Mark has seen his endocrinologist twice using Vitalog. He uploads his new lab results from the visit last week. The parser adds three new biomarker records. The trend engine automatically updates. He opens "Prepare for appointment," selects Follow-up, and sees a focused delta: what changed since last time. The summary is half a page. He prints it and walks in. *(Note: follow-up delta summaries are scoped to v1 per architecture §11; capstone covers first-visit only.)*

---

## 📖 Scenarios

1. Mark uploads a clean PDF from Quest Diagnostics — biomarkers extracted with ≥95% accuracy, auto-accepted (composite confidence in auto-accept band)
2. Mark photographs a 2022 paper report in poor lighting — Textract confidence below fallback threshold, vision-LLM fallback runs, low-confidence fields land in review band for his confirmation
3. Mark uploads a document he already uploaded — duplicate detected in Normalization, both stored, user notified
4. Mark types "show me everything related to my diabetes" — HbA1c, fasting glucose returned as grouped trend with context cards
5. Mark asks about a biomarker not in his record — "We don't have any TSH results yet. Upload a lab report that includes this test."
6. Mark generates a Cardiology summary for a first visit — all relevant biomarkers, data gaps noted (no post-statin lipid panel), every numeric value structurally cited and verified (Mode A), no clinical recommendations
7. Mark annotates the generated summary before export — annotation styled distinctly from system-generated content
8. **Mark uses Vitalog through Claude Desktop (MCP) as the primary channel** — all intelligence available via natural language conversation; this is the capstone demo channel
9. **Mark uploads a discharge summary** — system classifies it as `recognized_unsupported`, retains the raw file, and returns a v1+ roadmap message (architecture §5.1)
10. **Mark accidentally uploads a personal photo** — system classifies as `not_supported`, **discards the raw file**, retains audit metadata only (architecture §7.6)

---

## 🕹️ User Flow

**Happy Path — Upload to Appointment Summary:**

1. Mark opens Vitalog **via Claude Desktop (MCP)**
2. Invokes "Upload health document"
3. Uploads PDF or image file
4. System classifies document type (`lab_report` / `recognized_unsupported` / `not_supported`) → routes to extraction pipeline or short-circuit
5. **Textract extracts text + tables**; Textract field confidence checked
6. If Textract confidence below fallback threshold → **vision-LLM fallback** (Claude with vision)
7. LLM Structurer (Claude Sonnet) returns biomarker candidates with field-level confidence
8. **Composite confidence** computed per field via `min(textract, llm, classification)`; three-band routing applied (architecture §5.1.1):
   - ≥ `THRESHOLD_AUTO_ACCEPT` (initial 95) → auto-accept, flows into trends
   - `THRESHOLD_REJECT` ≤ c < auto-accept (initial 70–94) → review band; stored as `verified_by='pending_user'`; surfaces for Mark's confirmation
   - < `THRESHOLD_REJECT` (initial 70) → not stored; document flagged for re-upload
9. **Normalization runs** (architecture §5.2): Tier 1 LOINC-aware alias lookup → unit conversion to canonical UCUM → duplicate detection → Tier 4 pending queue for unmatched biomarkers
10. Persistence: records stored with full provenance; raw doc retention follows classification (§Compliance below)
11. Confirmation card shown: "9 results added, 1 pending taxonomy review, 1 pending user review"
12. Mark navigates to trend view or types a natural language query
13. Trend displayed with condition-aware ranges and factual observations
14. Mark selects "Prepare for appointment"
15. Selects specialist type and visit type
16. System generates structured summary from his record (Summary Generator + Mode A citation verification)
17. Mark reviews, adds annotation, removes any unwanted section
18. Mark exports as **PDF, markdown, or JSON** (no plain text)
19. Summary saved to his record history

**Key Alternative Flows:**
- Review-band extraction → user confirmation surfaces between step 9 and trend flow (record not visible in trends until confirmed)
- Reject-band extraction → user prompted to re-upload a clearer document
- Duplicate detected → notification shown, both records stored, user can review
- `recognized_unsupported` classification → file stored, processing short-circuits, v1+ roadmap message returned
- `not_supported` classification → file discarded, audit metadata retained, rejection message returned
- Follow-up visit → delta calculated from last saved summary (v1; capstone scope = first-visit only)

---

## 🧰 Functional Requirements

| SECTION | SUB-SECTION | USER STORY & EXPECTED BEHAVIORS | OUTPUT SURFACE |
|---------|-------------|----------------------------------|----------------|
| **Document Upload** | File selection | Mark selects one or more files (PDF, JPG, PNG, HEIC). System validates format and size. Returns upload acknowledgement. | MCP tool response |
| **Document Upload** | Classification | System classifies into three top-level categories: `lab_report`, `recognized_unsupported`, `not_supported` (architecture §5.1). Rich subtype captured in audit log for v1 expansion. Conservative bias toward `not_supported` under uncertainty. | MCP tool response |
| **Extraction** | OCR strategy | **AWS Textract** is the primary path; **Claude vision-LLM fallback** runs when Textract field confidence falls below `THRESHOLD_FALLBACK` (architecture ADR-02). LLM never sees the document image in the primary path. | Internal |
| **Extraction** | Clean PDF | LLM Structurer produces biomarker candidates with field-level confidence. **Three-band model** applied to composite confidence: auto-accept (≥95), review (70–94), reject (<70). Boundaries are named constants calibrated week 2 (architecture §5.1.1, Appendix D). | Results card via MCP |
| **Extraction** | Image/scan | Same pipeline with vision-LLM fallback invoked. Review-band records surface for user confirmation before flowing into trends. | Review prompt via MCP |
| **Extraction** | Confidence bands | Auto-accept band flows into trends. Review band stored as `verified_by='pending_user'`, surfaces in review queue. Reject band not stored; document flagged. | MCP review prompt |
| **Normalization** | Canonical naming | Raw test name resolved to `vitalog_id` via Tier 1 LOINC-aware alias lookup. Unmatched candidates go to Tier 4 pending taxonomy queue (architecture §5.2). Tiers 2 and 3 deferred to v1. | Internal |
| **Normalization** | Unit conversion | Raw unit → canonical UCUM unit using stored conversion rules. Out-of-range values flagged. Deterministic — no LLM in this path. | Internal |
| **Normalization** | Duplicate detection | Same canonical_id + same collection_date + value within tolerance → duplicate. Both stored. User notified. Neither auto-deleted. | Notification via MCP |
| **Normalization** | Pending taxonomy queue | Unmatched biomarkers staged for admin review with raw name, candidate LOINC codes, similarity scores. Capstone scope: founder resolves queue manually. | Internal (founder-only) |
| **Safety — AI Gateway** | Single chokepoint | Every LLM call routes through the AI Gateway with versioned prompts, model routing, and layered guardrails (architecture §7.1). No service calls Anthropic directly. | Internal |
| **Safety — Guardrails L1/L2/L3** | Layered defense | Layer 1 (input PII redaction + injection detection), Layer 2 (safety preamble + few-shot refusals + schema enforcement), Layer 3 (Pydantic schema validation + banned-phrase regex + citation verification). LLM-as-judge deferred to v1 (architecture §12 limitation 14). | Internal |
| **Safety — Citation Mode A** | Summary Generator | Every numeric biomarker value emitted by the Summary Generator must be wrapped in a structured citation object `{value, unit, collection_date, source_record_id}`. Deterministic lookup against retrieval set; unverifiable citations cause atomic rejection of the entire generation (architecture §7.2.1). | Internal |
| **Safety — Citation Mode B** | Observation + NLQ | Numeric tokens in prose output are parsed and matched against the retrieval set with ±0.5% tolerance for decimals; unmatched numerics cause rejection (architecture §7.2.1). | Internal |
| **Trend View** | Longitudinal chart | Mark views all results for one biomarker as a line chart. X-axis: date. Y-axis: canonical value. Condition-specific target range shown as shaded band (preferred over generic reference range). Source lab labeled per point. Pure code, no LLM. | MCP tool response |
| **Trend View** | Natural language query | Mark types any question. NLQ Handler retrieves relevant records deterministically first, then composes an answer grounded only in Mark's stored data. Graceful fallback when data missing. Mode B citation verification applied. | MCP tool response |
| **Trend View** | Context cards | Each biomarker has a context card: plain-language definition, relevance to Mark's conditions, published target range with source citation (ADA / ACC / AHA / ATA). | MCP tool response |
| **Appointment Prep** | Summary generation | Mark selects specialist type and visit type. Summary Generator composes structured summary from patient profile + condition profile + retrieved relevant records. Mode A citation verification is binding. Disclaimer always included. | MCP tool response |
| **Appointment Prep** | Patient annotation | Mark can add free-text notes to any section. Annotations styled distinctly from system content in exported output. | MCP tool response |
| **Appointment Prep** | Export | Mark exports as **PDF, markdown, or JSON**. Every export includes disclaimer and generation timestamp. | `export_summary` MCP tool |
| **Patient Profile** | Onboarding | Mark enters: known conditions, current medications (name + start date), allergies. Used to contextualize trends and summaries. Not extracted from documents in v1 (architecture assumption). | MCP tool response |

---

## 📐 Model & Stack Requirements

Model, runtime, OCR provider, persistence, schema validation, and provider strategy are specified in [`Vitalog_architecture.md` §9 (Technology Choices)](Vitalog_architecture.md) and §10 (ADRs). Capstone commits to **single-provider Anthropic** for all LLM calls (ADR-08, architecture §11). Multi-provider stub adapters exist in the AI Gateway but are deferred to v1.

This PRD does not duplicate the stack table — see architecture §9. Refer to architecture for: Python 3.11+ runtime, AWS Textract OCR, Claude Sonnet for structuring/generation, Claude with vision for OCR fallback, Supabase (Postgres + Storage), Pydantic for schema validation, Anthropic Python MCP SDK, custom Python eval harness.

---

## 🧮 Data Requirements

- **Canonical biomarker taxonomy** seeded with ~30 entries (architecture §5.2). Each entry carries: `vitalog_id`, canonical name, LOINC code, UCUM unit, unit conversions, aliases, condition mappings, guideline ranges with citations.
- **Reference data** shipped as versioned JSON in repo (architecture §6.3): LOINC subset, UCUM units, biomarker taxonomy seed, condition→biomarker map, specialist content templates, ADA/ACC/AHA/ATA guideline ranges.
- **Provenance for every record**: original name, value, unit, range (as-extracted) + canonical name, value, unit (post-normalization) + document_id, lab source, collection date, extraction confidence, `verified_by` (auto / user / admin / pending_user).
- **Storage retention is classification-gated** (architecture §7.6) — `lab_report` and `recognized_unsupported` retained permanently; `not_supported` discarded after classification with audit metadata preserved. **This supersedes v1 PRD's blanket "never deleted" rule.**
- **Patient profile data**: conditions, medications, allergies — entered by Mark, not inferred.
- **No real un-redacted PHI on the system for capstone** — synthetic + redacted data only (architecture §7.4).
- **Retention for capstone**: all medical data retained indefinitely; user-initiated deletion flow deferred to v1.

---

## 💬 Prompt Requirements

All prompts are invoked through the AI Gateway with layered guardrails (architecture §7.1, §7.2). Citation verification (Mode A / Mode B per architecture §7.2.1) is a binding constraint on Summary, Observation, and NLQ outputs.

**Extraction / Structurer prompt:**
- Input: Textract output (text + tables + KV pairs)
- Output: structured JSON per biomarker — name, value, unit, reference range, date, lab, field-level confidence
- Hard constraint: structure only what's visible; never interpret or recommend
- Confidence scoring: field-level, 0–100

**Classification prompt:**
- Output: `ClassificationResult(category, subtype, confidence, reasoning)` — three top-level categories plus rich subtype
- Conservative bias: default to `not_supported` under uncertainty
- Prompt written for full v1 subtype taxonomy; capstone routes only on top-level category

**Observation generation prompt (Intelligence §5.4.2):**
- Output: 1–3 plain-language sentences per biomarker
- Hard constraints: factual only, no clinical inference, no recommendations, no cause attribution, no predictions
- Citation: any numeric value mentioned must trace to source records (Mode B parse-and-match verification)
- Must cite published guideline source for any range referenced

**Summary generation prompt (Intelligence §5.4.4):**
- Output: structured sections (conditions, medications, results, trends, data gaps, patient notes, questions)
- Hard constraints: no diagnostic language, no treatment suggestions
- **Output must conform to structured-citation tool-use schema; every numeric biomarker value wrapped in a citation object `{value, unit, collection_date, source_record_id}`. Unverifiable citations cause atomic rejection of the generation (Mode A).**
- Disclaimer always included
- Personalization: specialist type + visit type + condition profile drive content selection

**Query handler prompt (Intelligence §5.4.3):**
- Must answer only from Mark's stored data — never from general medical knowledge alone
- Retrieval-first: relevant records pulled deterministically before LLM is called
- **Output passes through Mode B parse-and-match verification; unmatched numerics cause rejection**
- Graceful fallback if data not available

---

## 🧪 Testing & Measurement

**Offline (before demo):**
- **Eval corpus of ~18 documents** combining templated-synthesis PDFs (LLM generates content, templates render layout) + 3–5 redacted real reports (architecture ADR-07). The JSON used to render synthesized documents *is* the ground truth.
- Extraction accuracy: compare parsed output to ground truth per field
- **Confidence band boundaries calibrated in week 2** against the eval set following the methodology in [architecture Appendix D](Vitalog_architecture.md): boundary search over candidate `THRESHOLD_AUTO_ACCEPT` (90/92/95/97/99) and `THRESHOLD_REJECT` (60/65/70/75/80) with precision/recall reported
- Initial pass targets (inputs to calibration, not pass/fail gates): ≥95% accuracy on clean PDFs, ≥85% on photographed reports
- **Adversarial prompt suite** (architecture §7.2 Layer 4): 20+ examples designed to elicit clinical inference; regression-tested before any prompt change ships
- Observation quality review: 20 generated observations reviewed manually for factual accuracy and no clinical inference
- Summary review: 10 generated summaries reviewed manually for citation correctness, no diagnostic language, no treatment suggestions

**Online (demo):**
- Run full Mark scenario end-to-end: 9 HbA1c data points across 3 labs → trend view → specialist summary → PDF export
- Confirm zero clinical recommendations appear anywhere
- Confirm every value in summary is traceable to a source record (Mode A verification active)
- Confirm pending taxonomy queue is empty at demo time

**Rollback criteria:**
- If extraction accuracy falls below 85% on any document type → route records to review band rather than auto-accept
- If observation generation produces any clinical recommendation in adversarial testing → prompt revision required before demo
- If Mode A citation verification fails on >2% of synthesized summaries → block summary release until prompt or schema is fixed

---

## ⚠️ Risks & Mitigations

| RISK | MITIGATION |
|------|------------|
| LLM hallucinates biomarker values not present in document | Textract-primary OCR keeps LLM away from raw images in the main path (ADR-02); composite confidence scoring; user verification on review-band records |
| Clinical recommendation slips through Observation / Summary prompts | Layered guardrails (architecture §7.2); banned-phrase regex; Mode A/B citation verification; adversarial regression suite. **LLM-as-judge is not built for capstone** (see below). |
| **LLM-as-judge guardrail not in capstone scope** | Acknowledged in architecture §12 limitation 14 as the most significant unmitigated capstone safety gap. Primary defenses are Layer 2 prompt constraints + banned-phrase regex; Layer 2 is known to be insufficient under prompt drift and adversarial framing. Highest-priority v1 deferred item; required before any launch with real users. |
| **Single-provider Anthropic dependency** | Acknowledged in architecture §12 limitation 2. Anthropic API outage = product down for capstone. Mitigated in v1 with multi-provider routing via AI Gateway stub adapters. |
| **Mode A citation verifier does not validate arithmetic on derived values** | Architecture §12 limitation 11. A miscalculated delta ("HbA1c improved by 0.4%") would pass Mode A if both endpoint records exist. Mitigation in capstone: prompt restricts derived statements to a small whitelist of forms (delta, percent change, comparison-to-target). Full arithmetic verification deferred to v1. |
| **Mode B does not catch hallucinated qualitative claims or date mismatches** | Architecture §12 limitations 12, 13. Banned-phrase regex catches obvious qualitative claims; date verification deferred to v1; cross-biomarker numeric collisions partially mitigated by unit-consistency check. |
| OCR quality too low for photographed documents | Composite confidence scoring surfaces low-quality extractions; vision-LLM fallback path; user can manually correct review-band records |
| 3-week timeline too tight for all three masterplans | Masterplan 1 (Ingestion + Normalization) is prerequisite; Masterplan 2 (Intelligence) delivers core demo value; Masterplan 3 (Appointment summary) can be scoped to a single specialist if needed |
| Guideline ranges misapplied (wrong range for Mark's condition) | Static guideline library curated manually; cited to published source; not LLM-generated. Condition-specific range overlay strategy is a documented open question (architecture §12 OQ1) |
| HIPAA / medical data liability at demo | Synthetic + redacted data only for capstone; patient-controlled; no data sharing without explicit export; clear disclaimer on all outputs; no clinical advice |

---

## 💰 Costs

**Development (capstone):**
- LLM API costs: estimated low-volume usage (~$20–50 total for development + testing)
- AWS Textract: free tier expected to cover capstone document volume
- Supabase Free tier expected to cover capstone storage + database needs
- No external observability stack costs (deferred to v1 per architecture §7.3)

**Operational (post-launch estimate):**
- Token cost per document upload: ~$0.01–0.05 depending on document length and model
- Token cost per summary generation: ~$0.02–0.08
- Supabase Team + HIPAA add-on: ~$950/mo when v1 launches with real users (architecture ADR-04)
- Textract per-page costs and Anthropic enterprise BAA costs become material at scale

---

## 🔗 Assumptions & Dependencies

- **[ASSUMPTION]** Primary user is an adult (35–65) managing 2+ chronic conditions across 2+ providers, tech-comfortable but not tech-native
- **[ASSUMPTION]** **Demo channel is Claude Desktop via MCP**; CLI is fallback if MCP integration has quirks (architecture ADR-08)
- **[ASSUMPTION]** No FHIR or portal connections for capstone — upload-only ingestion
- **[ASSUMPTION]** "Contextual health tips" feature deferred to v2
- **[ASSUMPTION]** Medications and conditions entered manually by Mark during onboarding — not extracted from documents for v1
- **[ASSUMPTION]** Capstone covers first-visit summary; follow-up delta summaries are v1
- **[DEPENDENCY]** Anthropic API availability + stability during demo (used for classification, structuring, vision fallback, observations, NLQ, summaries)
- **[DEPENDENCY]** AWS Textract availability + free tier coverage during capstone
- **[DEPENDENCY]** Supabase Free tier availability for Postgres + Storage during capstone
- **[DEPENDENCY]** Static guideline library + LOINC subset + UCUM table built and validated before Masterplan 2 testing begins

---

## 🔒 Compliance / Privacy / Legal

- All health data is patient-uploaded and patient-controlled — Vitalog does not pull data from any external system without explicit user action
- **Storage policy is classification-gated** (architecture §7.6): `lab_report` and `recognized_unsupported` raw files retained permanently; `not_supported` raw files discarded after classification with audit metadata preserved. This supersedes any prior blanket retention rule.
- No data shared with third parties except the LLM API (Anthropic) and OCR provider (AWS Textract) — standard API data handling terms apply for capstone; BAAs required before v1 launch with real users
- Every output includes a clear disclaimer: *"This summary was prepared by Vitalog from patient-uploaded records. It is not a medical document and does not constitute medical advice. Please verify all information with your healthcare provider."*
- Product does not provide clinical recommendations, diagnoses, or treatment suggestions — hard constraint enforced at the prompt level AND the citation-verification layer
- For capstone: no formal HIPAA compliance required (research/demo context, synthetic data only); HIPAA compliance path assessed before v1 launch (architecture §7.4: Supabase Team + HIPAA add-on, BAA with Anthropic, BAA with AWS)
- Data retention and user-initiated deletion flow deferred to v1
- All published guideline ranges (ADA, ACC, AHA, ATA) cited to their source — no proprietary clinical content

---

## 📣 GTM / Rollout Plan

**Week 1 — Foundation:**
- **AI Gateway scaffold**: prompt registry skeleton, model router, Pydantic schemas, eval logger
- **Synthetic data generator script** + initial eval corpus (~18 docs combining templated synthesis + 3–5 redacted real reports)
- Masterplan 1: file upload endpoint, document classification (three-category) via AI Gateway
- Masterplan 1: AWS Textract integration, vision-LLM fallback path
- Masterplan 1: LLM Structurer prompt, composite confidence scoring, raw-doc storage policy (classification-gated)
- Repository pattern scaffolding for Persistence service

**Week 2 — Intelligence:**
- **Confidence band calibration** against eval set per architecture Appendix D — `THRESHOLD_AUTO_ACCEPT` and `THRESHOLD_REJECT` set with reported precision/recall
- **Normalization service**: Tier 1 LOINC-aware alias index + Tier 4 pending taxonomy queue + UCUM unit conversion table + duplicate detection
- Masterplan 2: biomarker taxonomy seed (~30 entries) + condition→biomarker map + guideline ranges JSON
- Masterplan 2: Trend Engine (pure code, no LLM)
- Masterplan 2: Observation Generator prompt + Layer 3 guardrails (banned-phrase regex, schema validator)

**Week 3 — Appointment Layer + Safety + Demo Polish:**
- Masterplan 2: NLQ Handler + context cards + Mode B citation verifier
- Masterplan 3: specialist content template (capstone: starts with cardiology; specialist count inherits architecture §11 scope of 1–2)
- Masterplan 3: Summary Generator prompt + **Mode A structured-citation verifier** + Layer 3 guardrails
- Masterplan 3: patient annotation flow, PDF/markdown/JSON export, disclaimer
- MCP server: wire up the 6 tools from architecture §5.7 (`upload_document`, `list_biomarkers`, `get_trend`, `query_records`, `prepare_summary`, `export_summary`)
- Pre-demo: resolve pending taxonomy queue (architecture §12 OQ5); end-to-end rehearsal of Mark's scenario; adversarial prompt regression run

**Demo Slice:**
Single end-to-end flow via Claude Desktop — upload 3 lab documents → view HbA1c trend → generate one-page specialist summary → export as PDF. This is the story. Everything else is infrastructure that makes this moment possible.

**Post-Capstone (v1 launch):**
- Web UI layer on top of the channel-agnostic value layer
- **LLM-as-judge guardrail** (highest-priority deferred safety item)
- LOINC Tiers 2 and 3 (fuzzy + live lookup)
- Multi-provider LLM routing (real adapters wired)
- Per-signal confidence calibration (independent thresholds)
- Follow-up delta summaries
- Expanded specialist coverage
- Full Safe Harbor PII redaction pipeline
- Supabase Team + HIPAA add-on + BAA with Anthropic + BAA with AWS
- Formal HIPAA risk assessment
- Expanded classification taxonomy (per-subtype processing pipelines)
- User-initiated deletion of stored documents

**v2 / scale:**
- FHIR / portal integration (MyChart, Quest, LabCorp)
- AWS migration from Supabase (triggers in architecture ADR-04)
- Contextual health tips feature with citations and disclaimers
- Provider-facing features
- Admin dashboard for taxonomy curation
- External observability stack (Datadog, Sentry)
