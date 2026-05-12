# Vitalog — Roadmap Document

| Field | Value |
|---|---|
| **Version** | 1.0 (Final) |
| **Date** | May 2026 |
| **Author** | Solo Founder |
| **Status** | Living document — updated as decisions evolve |
| **Companion documents** | `vitalog_prd.md`, `vitalog_architecture.md`, `decisions.md` |

---

## 1. Document Purpose & How to Use

### Purpose

This document captures the phase-by-phase evolution of Vitalog from capstone draft to mature product. Its primary jobs are:

1. **Preserve deferred decisions.** Throughout architectural design, dozens of items were explicitly cut from earlier phases for good reasons. Without a structured place to capture them, they get forgotten. This document is the canonical record of "what we agreed not to build yet, and when it should come back."
2. **Make phase boundaries explicit.** Each phase has clear entry triggers, scope, exit criteria, and risks. This prevents scope creep ("should this go in capstone?") by making the answer look-up-able rather than negotiated.
3. **Surface dependencies between phases.** Some v1.5 work requires v1 work first. Some v2 work depends on having real-user data. Making these explicit prevents accidental ordering mistakes.
4. **Provide a credible product narrative.** For capstone reviewers, mentors, and (eventually) investors or collaborators, this document shows that Vitalog has thought beyond the demo into a defensible product trajectory.

### How to use it

- **For capstone scope decisions:** Section 4 is the contract. If something isn't in Section 4, it doesn't ship in capstone. Period.
- **For mid-build temptations to add features:** When you find yourself wanting to build something cool, check whether it's in a later phase. If yes, resist; if no, add it to a phase explicitly before building.
- **For tracking deferred items:** Every architectural conversation that ended with "let's defer this to v1" should result in an item in the v1 section. If you can't find it here, it's not actually deferred — it's lost.
- **For revisiting decisions:** Section 10 (Decision Triggers) defines what events should cause you to re-open earlier choices. Use these as honest checkpoints, not excuses for scope creep.

### Living document discipline

This roadmap is updated as decisions evolve. When something moves between phases, when a trigger fires, or when scope shifts, update this document **before** updating the code. The discipline of writing the change down forces you to defend it.

Major version bumps (1.0 → 2.0) are reserved for fundamental shifts in product direction (e.g., pivoting from patient-facing to provider-facing). Minor bumps (1.0 → 1.1) are for phase additions, scope movement, or trigger updates.

---

## 2. Roadmap Philosophy

Three principles guide what goes into which phase. When tradeoffs surface, these principles win.

### Principle 1 — Ship the smallest defensible thing

Each phase ships the smallest version of the product that defensibly delivers value to its target users with acceptable safety guarantees. "Defensible" is the load-bearing word: capstone's defensibility is methodological rigor (eval-driven development, layered guardrails, honest accuracy reporting), not feature breadth. v1.5's defensibility is HIPAA compliance and real-patient safety, not feature parity with mature products.

### Principle 2 — Prove before scaling

No feature graduates from one phase to the next without evidence that it works. Capstone proves the value layer with synthetic data. v1 proves the product loop with real users (synthetic data + friends/family). v1.5 proves HIPAA-grade reliability with real patients. Each phase generates the evidence the next phase needs.

The corollary: **don't build for users you don't have yet.** Multi-tenant scaling concerns don't belong in v1. FHIR integrations don't belong in v1.5. Provider-facing features don't belong in v2 unless v2's user base demands them.

### Principle 3 — Decisions visible, deferrals explicit

If a feature was discussed and rejected for the current phase, it gets recorded in a later phase with the reasoning. Discarded ideas (RAG, agent-driven workflows) are recorded in `decisions.md` even if they don't make it onto the roadmap. The default is **make the decision visible**, never let it disappear into a side conversation.

---

## 3. Phase Overview

Five phases, each with a distinct identity, target user, and exit criteria.

| Phase | Duration | Target user | Defining property |
|---|---|---|---|
| **Capstone** | 3 weeks | The founder (Mark persona used as proxy) | Defensible value layer with evaluated accuracy; MCP-first demo |
| **v1 — Early users** | ~6–8 weeks post-capstone | Friends, family, founder network (≤20 users); synthetic + redacted data only | Web UI on top of the value layer; real product loop validated |
| **v1.5 — Real patients (HIPAA)** | ~3–4 months post-v1 | Real chronic-condition patients (≤200 users) with BAA-covered infrastructure | First production launch with real PHI; HIPAA-grade safety |
| **v2 — Integrations + provider features** | ~6+ months post-v1.5 | Same patients + their providers; FHIR-connected systems | Automation through portal integration; provider-facing surface |
| **Scale** | Open-ended | Hundreds to thousands of patients; enterprise considerations | Mature, multi-tenant, performance-tuned, compliant at scale |

The phases get progressively less specified as they extend further out. This is deliberate: **detail in distant phases rots faster than it's useful.** Capstone and v1 are specified precisely because they're imminent. Scale is sketched lightly because too much would be guessing.

---

## 4. Capstone (3 weeks)

### Goal

Ship a defensible end-to-end value layer demonstration: Mark uploads lab reports, sees a longitudinal HbA1c trend across multiple labs, and generates a one-page cardiology appointment summary — all via MCP, all with measured extraction accuracy and layered safety guardrails. Zero clinical recommendations anywhere in the output.

### Trigger to enter

Already entered. Capstone is the current phase.

### Scope (in)

**Ingestion**
- AWS Textract integration for primary OCR
- Claude Sonnet as LLM structurer
- Vision-LLM fallback (Claude with vision) for low-confidence Textract output
- Three-category document classification: `lab_report`, `recognized_unsupported`, `not_supported`
- Classifier returns rich subtype data (capstone routes only on top-level category)
- Pre-LLM probes (empty/corrupt file, no detectable text → fast reject)
- Conservative classification bias (uncertainty → `not_supported`)
- Three-band confidence model (auto-accept ≥95, review 70–94, reject <70) with composite confidence scoring (min of Textract, LLM, classification signals)
- Week-2 calibration of band boundaries against eval set (see architecture Appendix D)

**Normalization**
- Tier 1 (exact alias match) of the tiered resolution model
- Tier 4 (pending review queue) for unrecognized biomarkers
- ~30-biomarker seeded canonical taxonomy with LOINC codes + UCUM units + aliases + condition mappings
- Unit conversion for the units encountered in the test corpus
- Duplicate detection via (canonical_id, exact collection date, value tolerance)

**Persistence**
- Supabase Free tier
- Postgres for structured data (biomarker records, taxonomy, summaries, audit log)
- Supabase Storage for raw documents
- Repository pattern wrapping all Supabase access (migration-ready)
- Storage abstraction for raw documents
- Reference data shipped as JSON in repo (LOINC subset, UCUM, taxonomy seed, guideline ranges)
- Classification-gated storage policy: `not_supported` content discarded; everything else stored permanently

**Intelligence**
- Trend Engine (deterministic, no LLM)
- Observation Generator (LLM, guarded)
- Natural Language Query Handler (LLM, guarded, retrieval-first)
- Summary Generator for at minimum cardiology specialist + first-visit type
- Hero longitudinal data: Mark's 9-point HbA1c trend across 3 labs over 4 years (synthetic)

**AI Gateway and guardrails**
- Single chokepoint for all LLM calls
- Versioned prompt registry
- Layer 1: PII redaction for logs, basic prompt-injection pattern detection
- Layer 2: shared safety preamble, few-shot refusals, schema enforcement (tool use)
- Layer 3: banned-phrase regex filter, Pydantic schema validator, citation verifier (Mode A for summaries with structured citations; Mode B for prose outputs with parse-and-match)
- Eval logging on every LLM call

**Eval suite**
- Ground truth JSON for every test document (auto-generated for synthetic, manual for redacted real)
- Extraction accuracy pipeline (per-field precision/recall against ground truth)
- 20+ adversarial prompts targeting clinical advice elicitation
- Factuality eval on 50+ generated observations
- Test corpus of ~18 documents: 3–5 redacted real + 10 synthetic + 3 adversarial

**Top Layer**
- MCP server with 6 tools: `upload_document`, `list_biomarkers`, `get_trend`, `query_records`, `prepare_summary`, `export_summary`
- Demo channel: Claude Desktop

**Repo and tooling**
- `vitalog/` repo with the four-concerns folder structure
- Synthetic data generator script (`scripts/generate_synthetic.py`)
- One vendor-style template for synthetic PDF rendering (Quest-style)
- Manual PII redaction process for the 3–5 real reports

### Explicitly deferred from this phase

(N/A — capstone is the first phase. See later phases for what was deferred *out* of capstone.)

### Out of scope (deferred to later phases)

See Sections 5 (v1), 6 (v1.5), 7 (v2), 8 (Scale) for where each deferred item lives.

### Exit criteria

Capstone is complete when:

1. ✅ End-to-end demo runs cleanly on a fresh environment in under 5 minutes (upload → trend → cardiology summary → PDF export)
2. ✅ Mark's hero longitudinal flow exists: 9 HbA1c data points across 3 synthetic labs render as a single trend chart with ADA target range
3. ✅ Extraction accuracy measured and documented against ground truth corpus, with explicit acknowledgment of corpus size
4. ✅ Zero clinical recommendations appear in any generated output during full eval-suite run
5. ✅ All 20+ adversarial prompts return refusals
6. ✅ Citation verifier catches at least one real hallucination during testing (proof of working defense)
7. ✅ Final writeup complete: PRD, architecture doc, roadmap doc, eval results, risk register, future work
8. ✅ Demo recording captured as backup
9. ✅ Repo clean, README complete, AGENTS.md drafted for future Claude Code work

### Key risks

1. **Scope creep into Week 3.** Single biggest failure mode. Mitigation: weekly question — "Is this feature in the demo flow? If not, why am I building it this week?"
2. **Hero longitudinal data not generated until too late.** Demo flow depends on it. Mitigation: generate Mark's 4-year HbA1c progression on Day 1 of Week 3.
3. **Classification accuracy on borderline content unmeasured.** Eval corpus may not cover medical-adjacent edge cases. Mitigation: include 2–3 borderline documents in corpus; report classification accuracy per category.

### Business horizon

Capstone is pre-revenue, pre-user, pre-public. Goal is methodological credibility, not market traction.

---

## 5. v1 — Early users (~6–8 weeks post-capstone)

### Goal

Validate the full product loop with real users on real data — but with users where the consent and data scope are tightly controlled (founder network, friends, family). Synthetic + redacted data only; no un-redacted PHI yet. Add a web UI so non-MCP-fluent users can engage. Strengthen guardrails based on capstone learnings.

### Trigger to enter

- Capstone successfully demoed
- At least 5 friends/family identified as willing test users
- Founder commitment to 6–8 weeks of focused build + iteration

### Scope (in)

**New top layer**
- Web UI on top of the existing value layer (no architectural change to value layer)
- Authentication via Supabase Auth (basic email-based)
- Mobile-responsive design for upload and viewing
- Document deletion UX (user-initiated)

**Ingestion expansion**
- **Expanded classification taxonomy** — per-subtype categories at the routing layer (was deferred from capstone): `imaging_report`, `discharge_summary`, `visit_note`, `pathology_report`, `prescription`, `genetic_test_report`, plus the existing `lab_report` and `not_supported`
- **Subtype-specific user messaging** — each medical-but-unsupported document type gets a clear, type-specific rejection message with v2 roadmap context
- **Per-category storage policies** — e.g., consent-prompt before storing genetic test reports
- **Image content moderation** for inappropriate uploads (third-party API: AWS Rekognition or similar)

**Normalization expansion**
- **Tier 2: Fuzzy matching** — string similarity + embedding similarity against existing taxonomy (was deferred from capstone)
- **Tier 3: Live LOINC lookup** — query local LOINC database for genuinely new biomarkers (was deferred from capstone)
- **Confidence-based routing for taxonomy review** — high-confidence matches auto-link, medium-confidence triggers user prompt, low-confidence goes to admin queue (was deferred from capstone)
- **User-facing taxonomy review prompts** — non-blocking shadow processing model where users can confirm new biomarker mappings (was deferred from capstone)
- Expanded biomarker seed: ~100 biomarkers (up from ~30)

**Intelligence expansion**
- **LLM-as-judge guardrail layer** — added as Layer 3 component; second LLM scores generated content for advice/inference/prediction (was deferred from capstone, marked as stretch goal)
- **Expanded specialist coverage** — endocrinologist, primary care, internal medicine summary templates (was deferred from capstone; capstone shipped cardiology only)
- **Follow-up delta summaries** — "what changed since last visit" for recurring appointments (was deferred from capstone)
- **Improved retrieval for NLQ** — handle queries spanning multiple biomarkers more gracefully

**AI Gateway expansion**
- **Multi-provider LLM routing** with real adapters wired (capstone shipped stub adapters only) — initially for cost optimization (cheaper model for classification) and redundancy
- Anthropic remains primary; secondary provider added (likely OpenAI or Google) but not user-visible

**Eval expansion**
- Test corpus grows from ~18 to ~75 documents (more vendor diversity, more edge cases, more longitudinal patterns)
- Real-user feedback loop: when a user flags an extraction error, that document + correction graduates into the eval corpus
- Per-vendor accuracy reporting (Quest, LabCorp, hospital labs)
- Classification accuracy measured per-subtype

**Operational**
- Cost tracking dashboard for LLM tokens and Textract pages
- Basic application logs to Supabase Logs (not yet a full observability stack)
- Simple admin UI for reviewing pending taxonomy entries

**Repo and tooling**
- Multiple vendor-style templates for synthetic generator (Quest, LabCorp, hospital lab — capstone shipped one)
- More adversarial prompts in regression eval
- Smoke test suite covering all six MCP tools + web UI primary flows

### Explicitly deferred from capstone (now in scope)

- Expanded classification taxonomy (per-subtype categories)
- Per-category storage policies (e.g., consent-based storage for genetic data)
- Image content moderation for inappropriate uploads
- Subtype-specific user messaging
- User-initiated deletion of stored documents
- LOINC Tier 2 (fuzzy match) and Tier 3 (live LOINC lookup)
- Confidence-based routing for taxonomy review
- User-facing taxonomy review prompts
- LLM-as-judge guardrail layer
- Multi-provider LLM routing (real adapters wired)
- Web UI
- Follow-up delta summaries
- Expanded specialist coverage

### Out of scope (deferred to v1.5 or later)

- BAA-covered infrastructure (Supabase Team + HIPAA add-on)
- Real un-redacted PHI processing
- Formal HIPAA risk assessment
- Full Safe Harbor PII redaction pipeline
- FHIR / portal integrations
- Provider-facing features
- AWS migration

### Exit criteria

v1 is complete when:

1. ✅ At least 10 friends/family users have processed at least one document each
2. ✅ Web UI primary flow (upload → trend → summary → export) works end-to-end without MCP
3. ✅ Classification accuracy ≥90% per-subtype on expanded eval corpus
4. ✅ Tier 2 + Tier 3 taxonomy resolution working with confidence-based routing
5. ✅ At least one full prompt regression caught and prevented by the eval suite (proof of working regression discipline)
6. ✅ Real-user feedback loop has graduated at least 5 user-flagged corrections into the eval corpus
7. ✅ Multi-provider routing handles a 5+ minute Anthropic API outage transparently (tested via fault injection or observed organically)

### Key risks

1. **Real users surface unanticipated document varieties.** Capstone eval corpus is curated; real users upload chaos. Mitigation: aggressive corpus expansion in first 2 weeks of v1.
2. **Web UI work expands to fill available time.** Frontend is a known time sink. Mitigation: lock UI scope to the 4 primary flows; defer all nice-to-have UX to v1.5.
3. **LLM-as-judge produces too many false positives.** Subtle clinical inference is hard to define; the judge may flag legitimate output. Mitigation: tune judge against a labeled set before enabling in production; measure false-positive rate.
4. **Cost surprises from multi-provider routing.** Adding a second provider creates a second billing relationship with its own quirks. Mitigation: cost dashboard + alerts before enabling secondary provider in production traffic.

### Business horizon

Still pre-revenue. Goal is product validation: do real users find this valuable enough to come back? Retention beats acquisition at this stage.

---

## 6. v1.5 — Real patients (HIPAA-compliant) (~3–4 months post-v1)

### Goal

First launch with real chronic-condition patients and real un-redacted PHI. This is the phase where Vitalog stops being a research project and becomes a product handling people's medical data. Every piece of infrastructure, every BAA, every redaction pipeline, every audit trail must be production-grade.

This phase is **safety-defining**: a single PHI breach or clinical advice incident here ends the product.

### Trigger to enter

- v1 exit criteria met
- Founder is ready to commit to ongoing operational responsibility (HIPAA breach response, audit log review, etc.)
- Legal review of HIPAA posture complete
- Either: legal entity formation complete (LLC or similar) OR collaboration with an entity that can hold BAAs
- Pre-launch security review complete
- Real-patient user pool identified (≤200 users initial cap)

### Scope (in)

**Compliance and infrastructure**
- **Supabase Team + HIPAA add-on** (~$950/mo) — was deferred from v1
- **BAA executed with Supabase**
- **BAA executed with Anthropic** (enterprise plan or equivalent) — was deferred from v1
- **BAA executed with AWS** (covers Textract) — was deferred from v1
- **Formal HIPAA risk assessment** completed and documented — was deferred from v1
- **HIPAA policies and procedures documented** (breach notification, access controls, training, incident response)
- **Multi-factor authentication enforced** for all admin accounts; optional for users
- **Row-Level Security (RLS) audit** — every Postgres query scoped to `patient_id = auth.uid()`, verified

**PHI handling**
- **Full Safe Harbor PII redaction pipeline** — automatic detection and handling of the 18 HIPAA identifiers (was deferred from v1)
- Audit log enriched with redaction events
- Document-level encryption at rest beyond Supabase's default (application-level keys)
- Strict separation of redacted-for-LLM vs. full-fidelity-for-storage paths

**User-facing**
- User onboarding flow with informed consent and clear scope ("Vitalog is not a medical device; we don't provide medical advice")
- User-initiated data export (full record download)
- User-initiated account deletion with verifiable PHI purge

**Operational**
- External observability stack (Datadog, Sentry, or similar) — was deferred from v1
- 24-hour breach notification readiness
- Audit log review cadence (weekly initially)
- Cost monitoring at user-level granularity

**Quality bar**
- Zero clinical-advice incidents in production tolerated
- Extraction accuracy ≥95% on real-world (BAA-covered) lab reports
- Per-user audit trail accessible for any patient on request

### Explicitly deferred from v1 (now in scope)

- Supabase Team + HIPAA add-on
- BAA with Supabase
- BAA with Anthropic
- BAA with AWS / Textract
- Formal HIPAA risk assessment
- Full Safe Harbor PII redaction pipeline
- External observability stack

### Out of scope (deferred to v2)

- FHIR / portal integrations (MyChart, Quest, LabCorp APIs)
- Provider-facing features
- Auto-promote logic for canonical taxonomy entries (admin queue still bounded by founder time at this scale)
- AWS migration from Supabase
- Contextual health tips feature
- Telemedicine, scheduling, messaging features

### Exit criteria

v1.5 is complete when:

1. ✅ All required BAAs executed and on file
2. ✅ HIPAA risk assessment complete with mitigation plan
3. ✅ Safe Harbor redaction pipeline tested and verified on real documents
4. ✅ At least 50 real patients onboarded with consent
5. ✅ Zero clinical-advice incidents during launch period
6. ✅ Zero PHI breaches; audit log review process running weekly
7. ✅ Mean extraction accuracy ≥95% on BAA-covered real reports

### Key risks

1. **HIPAA posture gaps discovered post-launch.** Compliance is paperwork-heavy and easy to half-complete. Mitigation: external HIPAA consultant review before public launch; do not self-certify.
2. **Founder operational load.** HIPAA compliance is ongoing operational work, not a one-time setup. Mitigation: realistic time budget for compliance ops (likely 5–10 hours/week initially); consider compliance-as-a-service tools (Vanta, Drata).
3. **Cost shock from BAA-covered infrastructure.** Supabase Team + HIPAA + BAA-eligible Anthropic + observability tools = real money. Mitigation: cost model built and pressure-tested before commitment; clear path to revenue or funding.
4. **First clinical-advice incident.** A single bad output that's interpreted as medical advice is a significant credibility hit. Mitigation: layered guardrails are mature by this phase; LLM-as-judge is on by default; aggressive triage on any user-reported concern.

### Business horizon

This is the phase where revenue conversations become possible (subscription, freemium, etc.) — but should they happen here or be deferred until product-market fit is clearer? An open question, captured in Section 11.

---

## 7. v2 — Integrations + provider features (~6+ months post-v1.5)

### Goal

Move Vitalog from upload-driven to integration-driven. Patients no longer manually export from portals — Vitalog pulls directly. Add a provider-facing surface so doctors can review patient summaries with appropriate consent. Begin the journey toward being part of the care loop, not just a patient utility.

### Trigger to enter

- v1.5 has been operating stably for at least 3 months with no major safety incidents
- User base of ≥200 patients with ≥75% monthly active retention
- Clear demand signal for portal integration (most-requested feature, qualitative interviews)
- Founder bandwidth or team expansion sufficient for the engineering scope

### Scope (in)

This phase is intentionally less detailed than earlier ones. Detail will come when v2 is closer.

**Integrations**
- FHIR-based ingestion from major patient portals (MyChart / Epic, LabCorp Patient, Quest MyHealth)
- OAuth-based connection flow for patient consent
- Background sync of new lab results
- Reconciliation logic when portal data overlaps with previously uploaded documents

**Intelligence expansion**
- Support for unstructured medical content (visit notes, discharge summaries) — RAG becomes appropriate here
- "What did Dr. Patel say about my kidney function in November?" type queries become possible
- Cross-document reasoning over a patient's full record

**Provider-facing**
- Read-only provider portal where consented patients can share summaries
- Appointment-time summary access for the cardiologist, endocrinologist, etc.
- Provider feedback loop: "this summary was useful / could be improved"

**Taxonomy and operations**
- Auto-promote logic for canonical taxonomy entries (N independent confirmations or time-based promotion) — was deferred from v1.5
- Admin dashboard for taxonomy curation
- Expanded biomarker library to ~300 entries

**Possibly:**
- AWS migration from Supabase, if any of the documented triggers have fired
- Contextual health tips feature with hard guardrails (was in original PRD; deferred until safety story is mature enough)

### Explicitly deferred from v1.5 (now in scope)

- FHIR / portal integrations
- Auto-promote logic for canonical taxonomy entries
- Admin dashboard for taxonomy curation
- Provider-facing features
- Contextual health tips feature

### Out of scope

- Telemedicine
- Insurance integration
- Direct EHR write-back
- Anything that requires being a covered entity rather than a tool

### Exit criteria (sketch)

- FHIR integration working with at least 2 major portals
- ≥50% of new lab data arrives via integration rather than manual upload
- Provider-facing surface in use by at least one provider
- v1.5 retention metrics maintained or improved through the transition

### Key risks (sketch)

- FHIR integration is engineering-heavy and error-prone; portals have their own quirks
- Provider features expand the attack surface (provider auth, role separation, audit complexity)
- Scope expansion outpacing safety practices

---

## 8. Scale (open-ended)

### Goal

Mature, multi-tenant, performance-tuned product serving thousands of patients with enterprise-grade reliability and compliance.

### Trigger to enter

- v2 stable, with significant user growth (≥1000 active patients)
- Operational signals indicating Supabase or current infrastructure is approaching limits
- Possible enterprise opportunities (employer health programs, payer partnerships, research collaborations)

### Scope (sketch only)

- AWS migration if not already done (per documented triggers in architecture doc ADR-04)
- Multi-region deployment if patient distribution warrants
- Dedicated infrastructure for enterprise customers
- SOC 2 Type II compliance
- Performance optimization (caching, retrieval indexing, prompt caching)
- Mature observability and SRE practices
- Multi-tenant taxonomy with possible per-tenant customization
- Possibly: additional product surfaces (research data sharing, employer dashboards, etc.)

### Out of scope (probably forever)

- Direct clinical decision support (regulatory boundary)
- Replacement of EHR systems (different product, different market)
- Becoming a HIPAA-covered entity rather than a business associate (different regulatory posture)

### Exit criteria

Open-ended. Scale is a phase, not a destination.

---

## 9. Cross-Cutting Threads

Some capabilities don't live in a single phase — they evolve across all of them. Understanding their trajectory is more useful than scattering them across the per-phase sections.

### Taxonomy

| Phase | State |
|---|---|
| Capstone | ~30 manually-curated biomarkers; Tier 1 + Tier 4 only; admin queue handled by founder |
| v1 | ~100 biomarkers; Tier 2 + Tier 3 added; user-facing review prompts; confidence-based routing |
| v1.5 | Same as v1; bounded admin queue (~5–10 entries/week) |
| v2 | ~300 biomarkers; auto-promote logic on N confirmations; admin dashboard |
| Scale | Multi-tenant taxonomy; possible community curation; possible per-tenant overrides |

### Guardrails

| Phase | State |
|---|---|
| Capstone | Layers 1, 2, 3 (regex + schema + citation); LLM-as-judge stretch |
| v1 | LLM-as-judge enabled; expanded banned-phrase library; per-vendor regression testing |
| v1.5 | Production-grade incident response; zero-tolerance policy on clinical advice |
| v2 | RAG-specific guardrails for unstructured content (visit notes); provider-side guardrails |
| Scale | Continuous adversarial testing; red-team exercises; possibly external audit |

### Eval suite

| Phase | State |
|---|---|
| Capstone | ~18 documents; ground truth manual + auto-generated; 20+ adversarial prompts |
| v1 | ~75 documents; vendor-diverse; user-feedback graduation pipeline |
| v1.5 | ~200 documents including BAA-covered real reports; per-user accuracy tracking |
| v2 | Eval extends to FHIR-ingested data and unstructured content (visit notes) |
| Scale | Continuous eval pipeline; A/B testing prompts in production |

### Observability

| Phase | State |
|---|---|
| Capstone | Audit log to Postgres; structured stdout logs; basic cost tracking |
| v1 | Cost dashboard; admin UI for taxonomy review; basic application logs |
| v1.5 | Full observability stack (Datadog/Sentry); breach-readiness; weekly audit review |
| v2 | Provider-side observability; integration health monitoring |
| Scale | Mature SRE; SLOs; on-call rotation; chaos engineering |

### Channels

| Phase | State |
|---|---|
| Capstone | MCP only |
| v1 | MCP + Web UI |
| v1.5 | Same as v1 with mobile-responsive web; possibly native mobile |
| v2 | + Provider portal; possibly + WhatsApp/SMS for reminders |
| Scale | Whatever channels the product needs; possibly enterprise dashboards |

### LLM provider strategy

| Phase | State |
|---|---|
| Capstone | Single-provider (Anthropic) with stub adapters for v1 |
| v1 | Two-provider with real routing; primary Anthropic, secondary for cost/redundancy |
| v1.5 | BAA-covered providers only; multi-provider for redundancy |
| v2 | Provider mix optimized per task (e.g., specialized models for FHIR data) |
| Scale | Possibly fine-tuned models for specific tasks; cost-optimized routing |

### Data residency and storage

| Phase | State |
|---|---|
| Capstone | Supabase Free, US-region; synthetic + redacted only |
| v1 | Supabase Free, US-region; synthetic + redacted only |
| v1.5 | Supabase Team + HIPAA, US-region; real PHI under BAA |
| v2 | Same as v1.5 unless AWS migration triggered |
| Scale | Possibly multi-region; possibly AWS-native if any documented trigger fires |

---

## 10. Decision Triggers

Phase boundaries aren't always crossed by completing a checklist — sometimes external events force a re-think. This section captures the events that should cause us to revisit earlier decisions.

### Triggers to revisit AWS migration (currently planned post-v2 if at all)

Per architecture doc ADR-04, migrate from Supabase to AWS-native if any of:
- Monthly Supabase bill exceeds ~$2,500
- A specific control we need is not exposed by Supabase (e.g., dedicated infrastructure, custom KMS keys, specific data residency requirements)
- An enterprise customer requires AWS-native architecture as a condition of partnership
- Deep integration with AWS HIPAA services (HealthLake, Comprehend Medical) becomes valuable

### Triggers to revisit single-provider LLM strategy (currently scheduled for v1)

Move from stub multi-provider to real multi-provider routing earlier than v1 if:
- Anthropic API outage causes user-visible downtime in capstone or pre-v1 testing
- Cost optimization analysis shows >30% savings achievable via task-specialized routing
- A specific capability gap (e.g., handwriting accuracy on photos) makes a different provider materially better for one path

### Triggers to revisit MCP-first / channel strategy

Re-prioritize channels if:
- Capstone reviewers consistently express that MCP demo is hard to evaluate (could justify earlier web UI)
- A target user segment (older, less tech-fluent) emerges where WhatsApp / SMS is dramatically more accessible

### Triggers to accelerate v1.5 (HIPAA path)

Move HIPAA work earlier than planned if:
- A friend/family user wants to share Vitalog with someone who would require BAA coverage
- A regulatory complaint or near-miss surfaces that suggests current data handling is borderline

### Triggers to revisit provider features (currently v2)

Move provider-facing features earlier if:
- Multiple users independently report that their providers are asking for direct access
- A specific physician partner emerges as a design partner

### Triggers to revisit RAG decision (currently: not used)

Add RAG when:
- Visit notes / discharge summaries / pathology reports come into scope (likely v2) — RAG is the right pattern for unstructured medical content
- A specific use case emerges that genuinely cannot be served by structured retrieval

### Triggers to revisit non-agentic architecture decision (currently: not building agents)

Add agentic flows when:
- A use case emerges where the LLM genuinely needs to make multi-step decisions (e.g., proactive monitoring with tool selection) — most likely v2+
- The cost of building an agent is genuinely lower than building deterministic equivalents (rarely true; high bar)

### Triggers to bump roadmap version

Bump this document's version (1.0 → 1.1, 2.0, etc.) when:
- A major item moves between phases
- A new phase is added or split (e.g., if v1 grows large enough to split into v1.0 and v1.5 differently than currently)
- A trigger fires and the corresponding scope shift is material
- A fundamental product direction changes (major version bump)

---

## 11. Open Questions

Items where the future-state is genuinely uncertain, not yet decided. Captured here so they don't quietly become assumptions.

### Business model

- **When does monetization begin?** Probably v1.5 (real patients = real value), but could be deferred to v2 to focus on retention. Not decided.
- **What's the model?** Subscription, freemium, one-time, employer-sponsored, payer-sponsored — multiple plausible options, none committed.
- **B2C, B2B2C, or both?** Patient-pay vs. provider-or-employer-distributed has very different product implications.

### Regulatory posture

- **Will Vitalog ever pursue FDA pathways?** If contextual health tips or any decision-support adjacent feature is built, this becomes relevant. Currently: avoided. May not always be.
- **Is there a path to becoming a covered entity rather than a business associate?** Probably not (different product), but worth being explicit.

### Data scope

- **Should genetic test data be a v1 category or v2?** v1 deferral assumes most users don't have it; if friends-and-family pool skews differently, this could move earlier.
- **Should imaging report support ever be added?** Imaging requires very different parsing (DICOM, radiologist narrative). Possibly never — possibly v2+.

### Provider relationships

- **Does provider-facing belong in v2 or is it a separate product entirely?** Tightly coupling them risks making the patient product more complex without proportional value. Possibly a parallel product line.

### International

- **Will Vitalog be US-only or expand internationally?** LOINC and UCUM are international, but reference ranges, regulatory regimes, and lab vendors vary. Currently: implicitly US-only. Internationalization would be a major v2+ effort.

### Team

- **Will Vitalog remain solo, or does the founder hire / co-found?** Affects everything from scope velocity to compliance bandwidth. Not decided.

### Funding

- **Bootstrapped, grant-funded, VC-funded?** Each has very different roadmap implications. Currently: solo + capstone. Beyond capstone: open.

---

## 12. How to Update This Document

This roadmap is a living document. Updates should follow these rules:

1. **Update before building.** When you decide to move something from v1 to capstone (or vice versa), update this document *before* writing the code. The discipline of writing the change forces you to defend it.
2. **Update the version + date** in the header on any non-trivial change.
3. **Update the linked architecture doc** (`vitalog_architecture.md`) when scope changes affect the design — these documents must stay in sync.
4. **Add an entry to `decisions.md`** for any decision change material enough to warrant the roadmap update.
5. **Don't reorganize phases unnecessarily.** Phase identity stability matters for tracking. If something moves between phases, document the move; don't rename phases to make the move look less like a change.
6. **Be honest about deletions.** When a deferred item gets cut entirely (rather than moved to a later phase), record it in `decisions.md` as "scope cut" with the reasoning. Don't quietly delete from the roadmap.

### Versioning

- **Patch-level / no version change** — clarifications, typo fixes, additional detail in existing sections
- **Minor version bump (1.0 → 1.1)** — new phase content, scope additions or movements, new triggers
- **Major version bump (1.0 → 2.0)** — fundamental product direction change (e.g., pivot from patient-facing to provider-facing as primary)

### Review cadence

- Capstone phase: review weekly during the 3-week build
- v1 phase: review every 2 weeks during build
- v1.5 phase: review monthly
- v2 and Scale: review quarterly

---

## Appendix A — Quick reference: deferred items by destination phase

For when you're mid-build and need to look up "what did we decide to do with X?"

### Items deferred to v1
- Expanded classification taxonomy (per-subtype categories)
- Per-category storage policies (consent-based for genetic data, etc.)
- Image content moderation
- Subtype-specific user messaging
- User-initiated document deletion
- LOINC Tier 2 (fuzzy match)
- LOINC Tier 3 (live LOINC lookup)
- Confidence-based routing for taxonomy review
- User-facing taxonomy review prompts
- LLM-as-judge guardrail layer (highest-priority safety gap)
- Per-signal confidence calibration (independent thresholds for Textract, LLM, classification)
- Continuous re-calibration of confidence band boundaries
- Multi-provider LLM routing (real adapters)
- Web UI
- Follow-up delta summaries
- Expanded specialist coverage
- Real-user feedback loop into eval corpus

### Items deferred to v1.5
- Supabase Team + HIPAA add-on
- BAA with Supabase
- BAA with Anthropic
- BAA with AWS / Textract
- Formal HIPAA risk assessment
- Full Safe Harbor PII redaction pipeline
- External observability stack
- User-initiated full data export
- Application-level encryption beyond Supabase defaults

### Items deferred to v2
- FHIR / portal integrations (MyChart, Quest, LabCorp)
- Provider-facing surface
- Auto-promote logic for canonical taxonomy entries
- Admin dashboard for taxonomy curation
- Support for unstructured medical content (visit notes, discharge summaries)
- RAG for unstructured patient documents
- Contextual health tips feature
- Possibly: AWS migration (trigger-dependent)

### Items deferred to Scale
- Multi-region deployment
- Dedicated infrastructure for enterprise
- SOC 2 Type II compliance
- Multi-tenant taxonomy with per-tenant customization
- Continuous prompt A/B testing in production
- Mature SRE practices

### Items deferred indefinitely (or out of scope entirely)
- Telemedicine features
- Direct EHR write-back
- Becoming a HIPAA-covered entity
- Direct clinical decision support
- Replacement of EHR systems
- Insurance / billing integration
- RAG over the structured biomarker layer (architecturally rejected — see `decisions.md`)
- Agent-driven workflows in the value layer (architecturally rejected — see `decisions.md`)

---

*End of document.*
