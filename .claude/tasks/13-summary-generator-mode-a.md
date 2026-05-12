# Task 13 — Summary Generator + Mode A citation verification

## Context

The Summary Generator is the demo's payoff. Per architecture §5.4.4 + §7.2.1, summary output uses Anthropic **tool-use** to enforce a structured schema where every numeric biomarker value is wrapped in a `Citation` object `{value, unit, collection_date, source_record_id}`. **Mode A** verification does a deterministic lookup of each citation against source records; any unverifiable citation atomically rejects the entire generation. This is *the* safety story for the capstone — the citation verifier catching a real hallucination is roadmap §4 exit criterion #6.

## Dependencies

- Task 02 (Gateway — tool-use schema enforcement)
- Task 08 (persistence — lookup source records for citation verification)
- Task 11 (trend engine — feeds latest values into the summary context)
- Task 12 (Layer 3 + banned-phrase list — reused here)

## In scope

`src/intelligence/summary_generator.py`:

- `SummaryGenerator.generate(patient_id, specialist, visit_type) -> SummaryDocument`:
  - Capstone: `specialist="cardiology"`, `visit_type="first_visit"` only.
  - Load patient profile + retrieve relevant records (conditions + meds + last 6 months of records filtered by cardiology-relevant biomarkers).
  - Compose prompt context: condition profile, medications, retrieved records, specialist template.
  - Gateway call with `prompts/summary/cardiology_first_visit_v1.md`, tool-use enforced on `SummaryDocument`.
  - Every numeric biomarker value in any section must be a `Citation` object.
- `src/gateway/guardrails/citation_mode_a.py`:
  - `CitationVerifierModeA.verify(summary_document, source_records) -> ValidationResult`.
  - For each `Citation`:
    - Look up `source_record_id` in source records.
    - Compare `value` (exact), `unit` (string match against canonical), `collection_date` (exact).
    - Any mismatch → atomic reject of entire summary.
  - Limitation documented (architecture §12 #11): does not validate arithmetic on derived values; prompt restricts derived statements to a whitelist (delta, percent change, comparison-to-target).
- `prompts/summary/cardiology_first_visit_v1.md`:
  - Sections: Conditions, Medications, Recent Results, Trends, Data Gaps, Patient Notes, Questions for Doctor.
  - Hard constraints: no diagnostic language, no treatment suggestions, no recommendations.
  - Cardiology relevance: focus on lipid panel, HbA1c, BP-related context, kidney function.
  - Disclaimer always appended.
- `src/intelligence/export.py`:
  - `Exporter.export(summary, format) -> bytes`. Formats: `pdf` (reportlab), `markdown`, `json`. Disclaimer + generation timestamp included on every export.
  - Patient annotation rendered distinctly (markdown: blockquote; PDF: italic + colored).

## Out of scope (deferred)

- Multi-specialist coverage (v1).
- Follow-up delta summaries (v1).
- Arithmetic verification on derived values (v1; architecture §12 #11).
- LLM-as-judge (v1).

## Files to create

- `src/intelligence/summary_generator.py`
- `src/intelligence/export.py`
- `src/intelligence/retrieval.py` (relevant-record retrieval for cardiology)
- `src/gateway/guardrails/citation_mode_a.py`
- `prompts/summary/cardiology_first_visit_v1.md`
- `reference_data/specialist_templates/cardiology.json` (sections + relevant canonical_ids)
- `tests/intelligence/test_summary_generator.py`
- `tests/gateway/test_citation_mode_a.py`
- `tests/intelligence/test_export.py`

## Architecture references

- `docs/Vitalog_architecture.md` §5.4.4 — Summary Generator
- `docs/Vitalog_architecture.md` §7.2.1 — Mode A specification
- `docs/Vitalog_architecture.md` §5.7 — `prepare_summary` and `export_summary` MCP tools
- `docs/Vitalog_architecture.md` §12 #11 — Mode A arithmetic limitation
- `docs/Vitalog_PRD_v2.md` §Prompt Requirements "Summary generation"
- `docs/Vitalog_PRD_v2.md` §Functional Requirements "Appointment Prep" rows
- `docs/Vitalog_PRD_v2.md` §Risks "Mode A citation verifier does not validate arithmetic"

## Step-by-step

1. Write `reference_data/specialist_templates/cardiology.json` — sections, relevant canonical_ids, ordering.
2. Implement `Retrieval.get_relevant_records(patient_id, specialist)` — filter by canonical_id whitelist + date.
3. Write `prompts/summary/cardiology_first_visit_v1.md` — strong constraints + few-shot citation examples.
4. Implement `CitationVerifierModeA.verify` — deterministic lookup.
5. Implement `SummaryGenerator.generate` orchestration.
6. Implement `Exporter` for PDF/markdown/JSON.
7. Test: planted bad citation → Mode A rejects.
8. Test: clean generation → verified, exports cleanly to all 3 formats.

## Acceptance criteria

- [ ] Generated summary on hero data passes Mode A verification.
- [ ] Planted hallucinated citation (e.g., bad `source_record_id`) → atomic reject.
- [ ] Planted value mismatch (citation says 6.5, source has 6.8) → atomic reject.
- [ ] PDF export renders with disclaimer + timestamp + patient annotation styled distinctly.
- [ ] JSON export round-trips through `SummaryDocument` schema.
- [ ] No banned phrases in output.
- [ ] `mypy src/intelligence src/gateway --strict` clean.

## Verification

- `pytest tests/intelligence tests/gateway -q`
- `python -m src.intelligence.summary_generator mark cardiology first_visit` produces summary, exits 0.
- Generated PDF visually reviewed: disclaimer present, every numeric value cited, no recommendations.
- Adversarial test: mutate one citation in a fixture; assert rejection.
