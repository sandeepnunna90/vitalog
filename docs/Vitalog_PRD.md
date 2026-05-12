# Vitalog — Product Requirements Document

**Version:** 1.0 — Capstone Draft  
**Author:** Solo Founder  
**Date:** April 2026  
**Timeline:** 3 weeks to capstone submission

---

## 📝 Abstract

Vitalog is a patient-facing health intelligence tool that solves the fragmented medical records crisis. Americans managing chronic conditions see multiple specialists across multiple health systems, but their health data remains scattered across portals, paper reports, and memory. Vitalog gives patients like Mark — a 56-year-old managing Type 2 Diabetes, Hypertension, and a borderline thyroid condition — a single place to upload, understand, and present their health history. The product ingests documents in any format, extracts and normalizes biomarker data, builds longitudinal trend views with condition-aware context, and generates a one-page appointment summary a doctor can actually use. Built MCP-first for the capstone, with a web UI as a follow-on layer. Designed to scale into a real business.

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
- Mark can upload any lab document (PDF or photo) and see structured biomarker data within 15 seconds
- Mark can view a longitudinal trend for HbA1c across 9 data points from 3 different labs — on one chart
- Mark can generate a one-page cardiology appointment summary, add a personal note, and export it as PDF or markdown — in under 3 minutes
- Zero clinical recommendations appear anywhere in the product — only facts, published ranges, and observations
- End-to-end demo flow runs cleanly: upload → parse → trend → appointment summary

**Business (post-launch):**
- Mark walks out of every appointment understanding his full health trend
- Vitalog becomes the tool patients open before every appointment, not just once

---

## 🚶‍♀️ User Journeys

**Mark's Primary Journey — First Use:**
Mark downloads his latest HbA1c result from the Quest portal. He uploads it to Vitalog. Within seconds, he sees a structured card: test name, value, reference range, date, lab source. He navigates to the HbA1c trend view and sees — for the first time — all nine results from the last four years plotted on a single timeline with the ADA target line. He types "show me my diabetes markers" and sees HbA1c and fasting glucose grouped together with context cards explaining what each one means. He has a cardiology appointment on Friday. He selects "Prepare for appointment," chooses Cardiologist / First Visit, reviews the generated summary, adds a note about his recent statin start, and exports a PDF. He emails it to the cardiologist's office the night before. He walks in prepared.

**Mark's Recurring Journey — Follow-Up Visit:**
Mark has seen his endocrinologist twice using Vitalog. He uploads his new lab results from the visit last week. The parser adds three new biomarker records. The trend engine automatically updates. He opens "Prepare for appointment," selects Follow-up, and sees a focused delta: what changed since last time. The summary is half a page. He prints it and walks in.

---

## 📖 Scenarios

1. Mark uploads a clean PDF from Quest Diagnostics — biomarkers extracted with ≥95% accuracy, confirmed automatically
2. Mark photographs a 2022 paper report in poor lighting — OCR runs, low-confidence values flagged for his review
3. Mark uploads a document he already uploaded — duplicate detected, both stored, user notified
4. Mark types "show me everything related to my diabetes" — HbA1c, fasting glucose returned as grouped trend with context cards
5. Mark asks about a biomarker not in his record — "We don't have any TSH results yet. Upload a lab report that includes this test."
6. Mark generates a Cardiology summary for a first visit — all relevant biomarkers, data gaps noted (no post-statin lipid panel), no clinical recommendations
7. Mark annotates the generated summary before export — annotation styled distinctly from system-generated content
8. Mark uses Vitalog through a Claude interface (MCP mode) — same intelligence available via natural language conversation

---

## 🕹️ User Flow

**Happy Path — Upload to Appointment Summary:**

1. Mark opens Vitalog (web UI or MCP interface)
2. Selects "Upload health document"
3. Uploads PDF or image file
4. System classifies document type → routes to extraction pipeline
5. Biomarkers extracted, normalized, confidence-scored
6. Low-confidence values flagged for Mark's review → Mark confirms or corrects
7. Confirmation card shown: "3 new results added to your record"
8. Mark navigates to trend view or types a natural language query
9. Trend displayed with condition-aware ranges and factual observations
10. Mark selects "Prepare for appointment"
11. Selects specialist type and visit type
12. System generates structured summary from his record
13. Mark reviews, adds annotation, removes any unwanted section
14. Mark exports as PDF, plain text, or structured JSON
15. Summary saved to his record history

**Key Alternative Flows:**
- Low-confidence extraction → user review and correction step inserted between steps 5 and 6
- Duplicate detected → notification shown, both records stored, user can review
- Follow-up visit → delta calculated from last saved summary, only changed items shown in full
- MCP/headless mode → all steps handled via conversational tool calls, markdown output returned

---

## 🧰 Functional Requirements

| SECTION | SUB-SECTION | USER STORY & EXPECTED BEHAVIORS | SCREENS |
|---------|-------------|----------------------------------|---------|
| Document Upload | File selection | Mark selects one or more files (PDF, JPG, PNG, HEIC). System validates format and size. Shows upload progress. | Upload screen |
| Document Upload | Classification | System identifies document type: lab report, discharge summary, visit note, or unsupported. Unsupported files shown with explanation. | Auto |
| Extraction | Clean PDF | System extracts all biomarker fields with confidence ≥90%. Auto-accepted. Confirmation card shown. | Results card |
| Extraction | Image/scan | OCR runs first. Fields below 90% confidence flagged for user review with inline correction UI. | Review screen |
| Extraction | Duplicates | Duplicate biomarker detected (same test, ±30-day window). Both stored. User notified. Neither auto-deleted. | Notification |
| Trend View | Longitudinal chart | Mark views all results for one biomarker as a line chart. X-axis: date. Y-axis: value. Condition-specific target range shown as shaded band. Source lab labeled per point. | Trend screen |
| Trend View | Natural language query | Mark types any question. System returns grounded response from his record only. Unanswered queries explained gracefully. | Query input |
| Trend View | Context cards | Each biomarker has a tappable card: plain-language definition, relevance to Mark's conditions, published target range with source citation. | Context panel |
| Appointment Prep | Summary generation | Mark selects specialist type and visit type. System generates structured summary in <30 seconds. | Summary screen |
| Appointment Prep | Patient annotation | Mark can add free-text notes to any section. Annotations styled distinctly from system content. | Edit mode |
| Appointment Prep | Export | Mark exports as PDF, plain text, or JSON. Every export includes disclaimer and generation timestamp. | Export options |
| Patient Profile | Onboarding | Mark enters: known conditions, current medications (name + start date), allergies. Used to contextualize trends and summaries. | Profile setup |

---

## 📐 Model Requirements

| SPECIFICATION | REQUIREMENT | RATIONALE |
|---------------|-------------|-----------|
| Open vs Proprietary | Proprietary (Claude / OpenAI) | Reliability, document understanding, instruction-following quality required for medical context |
| Context Window | ≥32K tokens | Multi-page lab reports and full patient record context for summary generation |
| Modalities | Text + Vision | Vision required for photographed/scanned documents; text for structured extraction and generation |
| Fine Tuning | Not required for capstone | Prompt engineering sufficient; fine-tuning deferred to v2 if accuracy targets not met |
| Latency | P50 <10s per document; P95 <20s | User expectation set at "within 15 seconds"; summary generation <30s |
| Parameters | Not specified | Use hosted API; no self-hosted inference for capstone |

---

## 🧮 Data Requirements

- No fine-tuning for capstone — prompt engineering approach only
- Static reference data required: biomarker taxonomy (50+ canonical names), category mappings, condition-specific guideline ranges (ADA, ACC, AHA, ATA) stored as structured JSON, not LLM-generated
- Each biomarker record stored with full provenance: canonical name, value, unit, reference range, date, lab source, document ID, confidence score, verified-by flag
- Original uploaded documents stored alongside extracted records (never deleted)
- Patient profile data: conditions, medications, allergies — entered by Mark, not inferred
- No PII transmitted to third-party services beyond the LLM API (compliant with standard API data handling)
- Retention: all data retained indefinitely for capstone; data deletion flow deferred to v2

---

## 💬 Prompt Requirements

**Extraction prompt (Masterplan 1):**
- Output: structured JSON per biomarker — name, value, unit, reference range, date, provider, lab, confidence
- Hard constraint: extract only, never interpret or recommend
- Confidence scoring: field-level, 0–100

**Observation generation prompt (Masterplan 2):**
- Output: 1–3 plain-language sentences per biomarker
- Hard constraints: no clinical recommendations, no cause attribution, no predictions
- Must cite published guideline source for any range referenced
- Accuracy target: ≥98% factual correctness on test set

**Summary generation prompt (Masterplan 3):**
- Output: structured sections (conditions, medications, results, trends, data gaps, patient notes, questions)
- Hard constraints: no diagnostic language, no treatment suggestions, every value cited with date and source
- Must include disclaimer in every output
- Personalization: specialist type and visit type passed as context; condition profile drives content selection

**Query handler prompt (Masterplan 2):**
- Must answer only from Mark's stored data — never from general medical knowledge alone
- Graceful fallback if data not available: explain what's missing, suggest uploading relevant document

---

## 🧪 Testing & Measurement

**Offline (before demo):**
- Build ground truth set: 20+ real lab reports manually verified by founder
- Extraction accuracy: compare parsed output to ground truth per field
- Pass threshold: ≥95% accuracy on clean PDFs, ≥85% on photographed reports
- Observation quality review: 20 generated observations reviewed manually for factual accuracy and no clinical inference
- Summary review: 10 generated summaries across 3 specialist types reviewed manually

**Online (demo):**
- Run full Mark scenario end-to-end: 9 HbA1c data points across 3 labs → trend view → cardiology summary → PDF export
- Confirm zero clinical recommendations appear anywhere
- Confirm every value in summary is traceable to a source record

**Rollback criteria:**
- If extraction accuracy falls below 85% on any document type → flag to user rather than auto-accept
- If observation generation produces any clinical recommendation in testing → prompt revision before demo

---

## ⚠️ Risks & Mitigations

| RISK | MITIGATION |
|------|------------|
| LLM hallucinates biomarker values not present in document | Prompt constrains extraction to visible text only; confidence scoring flags uncertain values; user verification step for anything below 90% |
| Clinical recommendation slips through observation/summary prompts | Hard constraint language in every prompt; manual test suite of 20+ adversarial examples before demo |
| OCR quality too low for photographed documents | Confidence scoring surfaces low-quality extractions; user can manually enter or correct any value |
| 3-week timeline too tight for all three masterplans | Masterplan 1 is prerequisite; Masterplan 2 delivers core demo value; Masterplan 3 can be scoped to a single specialist type if needed |
| Guideline ranges misapplied (wrong range for Mark's condition) | Static guideline library curated manually by founder; cited to published source; not LLM-generated |
| HIPAA / medical data liability concerns at demo | Product is patient-controlled; no data sharing without explicit export; clear disclaimer on all outputs; no clinical advice |

---

## 💰 Costs

**Development (capstone):**
- LLM API costs: estimated low-volume usage during development and testing (~$20–50 total)
- No infrastructure costs if using free tiers of Supabase + Vercel or similar

**Operational (post-launch estimate):**
- Token cost per document upload: ~$0.01–0.05 depending on document length and model
- Token cost per summary generation: ~$0.02–0.08
- Storage: negligible at early user volumes
- At scale, inference cost is the primary variable — optimize with caching for static context cards and biomarker taxonomy

---

## 🔗 Assumptions & Dependencies

- **[ASSUMPTION]** Primary user is an adult (35–65) managing 2+ chronic conditions across 2+ providers, tech-comfortable but not tech-native
- **[ASSUMPTION]** LLM layer uses Claude (Anthropic) API for capstone; model choice can be revised
- **[ASSUMPTION]** No FHIR or portal connections for capstone — upload-only data ingestion
- **[ASSUMPTION]** For capstone, "contextual health tips" feature (v2 business feature) is out of scope
- **[ASSUMPTION]** Web UI is parallel or follow-on to MCP-first architecture; demo may be CLI or conversational
- **[ASSUMPTION]** Medications and conditions entered manually by Mark during onboarding — not extracted from documents for v1
- **[DEPENDENCY]** LLM API availability and stability during demo
- **[DEPENDENCY]** OCR library performance on low-quality photographed documents
- **[DEPENDENCY]** Static guideline library must be built and validated before Masterplan 2 testing begins

---

## 🔒 Compliance / Privacy / Legal

- All health data is patient-uploaded and patient-controlled — Vitalog does not pull data from any external system without explicit user action
- No data shared with third parties except the LLM API (standard API data handling terms apply)
- Every output includes a clear disclaimer: *"This summary was prepared by Vitalog from patient-uploaded records. It is not a medical document and does not constitute medical advice. Please verify all information with your healthcare provider."*
- Product does not provide clinical recommendations, diagnoses, or treatment suggestions — hard constraint enforced at prompt level
- For capstone: no formal HIPAA compliance required (research/demo context); HIPAA compliance path should be assessed before any real-world launch
- Data retention and deletion flow deferred to v2; no sensitive data stored on unsecured infrastructure
- All published guideline ranges (ADA, ACC, AHA, ATA) cited to their source — no proprietary clinical content

---

## 📣 GTM / Rollout Plan

**Week 1 — Foundation:**
- Masterplan 1: File upload endpoint, PDF text extraction, OCR integration, document classification prompt
- Masterplan 1: Biomarker extraction prompt, unit normalization, duplicate detection, database schema
- Begin building ground truth test set (20+ lab reports)

**Week 2 — Intelligence:**
- Masterplan 1: Confidence scoring, user review flow, storage + provenance
- Masterplan 2: Biomarker taxonomy, static guideline library, trend construction engine
- Masterplan 2: Observation generation prompt + quality testing

**Week 3 — Appointment Layer + Demo Polish:**
- Masterplan 2: Natural language query handler, context cards, MCP tool interfaces
- Masterplan 3: Specialty mapping, content selection, summary generation prompt
- Masterplan 3: Patient annotation, PDF/markdown export, disclaimer
- End-to-end demo rehearsal: Mark's full scenario (upload → trends → cardiology summary → PDF)
- Edge case testing and accuracy audit

**Demo Slice:**
Single end-to-end flow — upload 3 lab documents → view HbA1c trend → generate one-page cardiology summary → export as PDF. This is the story. Everything else is infrastructure that makes this moment possible.

**Post-Capstone (business launch):**
- Web UI layer on top of MCP-first architecture
- FHIR / portal integration (MyChart, Quest, LabCorp)
- Expanded specialty coverage and biomarker library
- "Contextual health tips" feature with published guideline citations and hard disclaimers
- HIPAA compliance assessment and legal review before handling real patient data at scale
