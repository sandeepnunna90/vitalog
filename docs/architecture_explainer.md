# Vitalog — Architecture Explainer

*Talking points for the demo. Plain language, layer by layer.*

---

## The Shape of the System

Every request flows through two independent stacks:

```
User uploads a file
        ↓
[ Ingestion ] → [ Normalization ] → [ Persistence ]
                                          ↓
User asks a question → [ Intelligence ] ← ↑
                                ↓
                        [ AI Gateway ]
                     L1 · L2 · L3 · Mode A · Mode B
```

The AI Gateway is not a separate service sitting to the side — every single LLM call passes through it. It's the chokepoint. Nothing reaches Claude without going through the gateway first, and nothing leaves without being verified.

---

## 1 — Ingestion

*What happens the moment a file arrives.*

**Step 1 — Validation**
Before anything else: is this file safe to process? The validator checks six things in order — MIME type must be one of PDF, JPEG, PNG, or HEIC; file size must be under 20 MB; the file must not be empty; the declared type must match the actual bytes (so a renamed `.exe` doesn't sneak through). If any check fails, the upload is rejected immediately with a clear error.

**Step 2 — Classification**
The system asks: is this actually a lab report? It uses a classifier that returns one of three categories:
- `lab_report` — proceed
- `recognized_unsupported` — it's a medical document (discharge summary, prescription), but not a lab report; file is retained for audit but not processed
- `not_supported` — not a medical document at all; metadata only, file discarded

The classifier has a conservative bias: if confidence is below 0.70, it flips the result to `not_supported` regardless of what the model thought. Better to reject a real report than to hallucinate structure from a grocery receipt.

**Step 3 — OCR**
For confirmed lab reports, text extraction happens in two passes. AWS Textract runs first — it's purpose-built for structured documents and handles tables well. If Textract confidence is too low, the system falls back to Claude Vision (the LLM itself reads the image). This fallback exists because some scanned handwritten forms or unusual layouts defeat OCR entirely.

**Step 4 — Structurer**
Raw OCR text isn't usable — it's a wall of strings. The structurer finds biomarker names, values, units, and reference ranges, then scores confidence on each extracted field. Three bands:
- ≥ 95 → auto-accept, written to the database
- 70–94 → flagged for review
- < 70 → rejected; not stored

This prevents garbage data from corrupting trend lines.

---

## 2 — Normalization

*Turning raw strings into queryable, comparable records.*

Lab reports are not standardised. "HbA1c", "Hgb A1c", "Hemoglobin A1c", "A1C" — these are all the same biomarker, printed differently by different labs.

**Alias Lookup**
The system maintains a taxonomy of 84 canonical biomarker names, each with a list of known aliases. The lookup is case-insensitive, whitespace-collapsed, and O(1) — it doesn't fuzzy-match, it uses a pre-built reverse index. When a name matches a known alias, it gets mapped to the canonical ID. Each canonical biomarker also carries a LOINC (Logical Observation Identifiers Names and Codes) code — the international standard identifier for clinical observations. Today LOINC codes are stored as audit-quality metadata; LOINC-based fuzzy matching for unknown names is on the roadmap for v1.

**Unit Conversion**
If the extracted unit doesn't match the canonical unit, the value is converted. Units are normalised to UCUM (Unified Code for Units of Measure) form — the international standard for clinical units. For example, glucose reported as mmol/L by one lab and mg/dL by another gets converted to a single canonical unit before being stored, so trend comparisons are valid across labs that use different measurement systems.

**Duplicate Detection**
If the same biomarker with the same collection date already exists in the database, the system detects the duplicate using a numeric tolerance (±0.5%) and skips re-insertion rather than creating duplicate records.

**Pending Queue**
This is the key design decision: unknown biomarker names are never silently discarded. If a name doesn't match anything in the taxonomy, it goes into a pending queue. An admin (me, in the demo) reviews the queue, maps the unknown name to its canonical ID, and all records associated with it are updated immediately — no re-upload needed.

In the demo: "25-OH Vitamin D" will land in the queue. I map it to `vitamin_d` with one command, and immediately a trend appears going back to 2019.

---

## 3 — Intelligence

*Turning stored biomarker records into useful answers.*

**Trend Engine**
Given a canonical biomarker ID and a patient ID, returns all readings in chronological order with reference band overlays (normal range, target range per condition). This is the engine behind every trend query in the demo.

**NLQ Handler (Natural Language Query)**
The user types a question in plain English. The NLQ handler figures out which biomarkers are relevant, retrieves the records, and asks the LLM to answer using only that data. Mode B citation verification (explained below) ensures the answer can't cite a number that isn't in the retrieval set.

**Observation Generator**
Generates a short observation per biomarker — e.g. "HbA1c has improved from 8.2% to 6.9% over 6 years, now within the ADA target of <7.0%." Each observation is also Mode B verified.

**Summary Generator**
Produces a one-page structured health summary covering all conditions present in the patient's records. This is the most strictly verified output — it uses Mode A (explained below), which requires every number to have a traceable citation object pointing to an exact database record. If the LLM invents a number, Mode A rejects the output and forces a retry.

**Export**
The summary can be exported as PDF (via WeasyPrint), Markdown, or JSON. The PDF is returned as base64 to the MCP client.

---

## 4 — Persistence

*Where data lives.*

All patient data lives in Supabase — a managed Postgres database. The system uses a repository pattern: application code never writes raw SQL; it calls repository methods that encapsulate the queries. This makes it straightforward to swap the backend without changing business logic.

Files (PDFs, images) go to Supabase Storage in a separate `lab_reports` bucket. The database row holds a reference to the storage path.

One design constraint: classification gates what gets stored. `not_supported` documents have their file discarded immediately after classification — only audit metadata is kept. This limits storage costs and avoids accumulating irrelevant files.

---

## 5 — AI Gateway

*Every LLM call passes through here. No exceptions.*

The gateway is a single Python class with three sequential guardrail layers, followed by citation verification on the output. Think of it as a firewall that checks the request going in and the response coming out.

---

### L1 — Input Sanitisation

**What it does:** Before the request reaches the LLM, L1 does two things:

1. **PHI Redaction (for logs):** Dates of birth, SSNs, phone numbers, email addresses, and other PII patterns are regex-stripped from the version that gets written to the eval log. The model still sees the original data — L1 doesn't alter what the LLM receives, it only protects the audit trail.

2. **Injection Detection:** Scans the input for prompt injection patterns — things like "ignore all previous instructions" buried inside a nested JSON field. If detected, it logs a warning. It never silently drops the request (that would hide attacks), but it flags them so they can be reviewed.

*In plain terms: L1 keeps logs clean and detects adversarial inputs before they reach the model.*

---

### L2 — Safety Preamble + Refusal Examples

**What it does:** Every prompt sent to the LLM is prefixed with a safety preamble that reminds the model of its role: Vitalog answers questions grounded in uploaded lab data — it does not diagnose, prescribe, or advise.

The preamble is loaded once at startup (not re-read per call). It includes three few-shot refusal examples covering:
- Medical advice requests
- Medication adjustment requests
- Diagnosis requests

These examples teach the model the *shape* of a correct refusal — so when a user asks "should I take more metformin?", the model has seen exactly what a good refusal looks like.

*In plain terms: L2 shapes model behaviour before it generates a word.*

---

### L3 — Deterministic Output Scanner

**What it does:** After the LLM responds, L3 checks the output before it's returned to the user. Two checks, run in this order:

1. **Schema Validation:** Is the response the correct Pydantic shape? If the tool expects a `SummaryOutput` and gets something else, L3 rejects it immediately. Schema is checked first because it's cheapest.

2. **Banned Phrase Scanner:** A regex scan against a list of prohibited phrases — clinical advice patterns, medication recommendations, diagnostic language. If any match, L3 captures the specific phrase(s) and triggers a retry with an explicit instruction: "you said X — do not say that."

*In plain terms: L3 is a final deterministic gate — regex doesn't hallucinate, so it catches what the model shouldn't have said.*

---

### Mode A — Structured Citation Verification (Summary)

**What it does:** Used by the Summary Generator. The LLM is given a retrieval set of biomarker records and asked to produce structured output where every numeric claim includes a citation object — a `source_record_id` pointing to an exact database row, plus the exact value it used.

After the LLM responds, Mode A walks every citation: it looks up the `source_record_id` in the retrieval set and checks that the value in the citation matches the stored value within ±0.5% tolerance. If any citation doesn't resolve — if the LLM invented a number — the entire output is rejected and the call retries.

The LLM cannot fabricate a biomarker value and have it reach the user. It either cites a real record or it fails.

*In plain terms: Mode A is the audit trail. Every number is traceable to a database row. Nothing fabricated gets through.*

---

### Mode B — Parse-and-Match Verification (NLQ + Observations)

**What it does:** Used by the NLQ Handler and Observation Generator. The output is prose, not structured citations — so Mode B works differently. It parses every number out of the LLM's response text and checks whether each number exists in the retrieval set (within ±0.5% tolerance for decimals, exact match for integers).

If the LLM mentions a value that isn't in the records it was given, Mode B flags it and triggers a retry.

One subtlety: units matter. Mode B uses a validity gate to reject false positives — things like the word "has" or "was" that a naive regex might parse as a unit. Real clinical units always contain a `%`, a `/`, a digit, or an uppercase letter.

*In plain terms: Mode B is a numeric consistency check. Every number the LLM mentions must be traceable to a real record.*

---

## What the gateway means in practice

During the demo, when I ask "what do my triglyceride and HDL levels say about my cardiovascular risk?" — here's the actual path:

1. Query enters the gateway
2. L1 scans for injection patterns, redacts any PII from the log copy
3. L2 prepends the safety preamble
4. NLQ handler retrieves the relevant records and sends them to Claude with a prompt
5. Claude responds with an answer
6. L3 scans the response for banned phrases and validates the schema
7. Mode B extracts every number from the prose and verifies each one exists in the retrieval set
8. If all checks pass, the answer is returned

If the LLM had said "you should take a statin" — L3 catches it. If it made up a cholesterol value — Mode B catches it. The user sees only what passed all five checks.
