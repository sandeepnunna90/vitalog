# E3 — Unit conversion + physiological-range validation

**Epic:** Normalization
**Points:** 3
**Priority:** Critical
**Depends on:** A2, E1
**Architecture refs:** §5.2 (Unit Conversion section); PRD v2 Normalization Unit conversion row

## User story

As Mark whose 2022 HbA1c was reported in `mmol/mol` while every other result is in `%`,
I want Vitalog to convert all units to a canonical UCUM unit using stored conversion rules,
So that my trend chart shows one consistent series and not two visually-disconnected ones.

## Why this matters

P4 (determinism where possible) puts unit conversion on the "must be deterministic" list. LLM-based unit conversion would be plausible but unreliable — and "wrong unit conversion corrupts data forever" (architecture §5.2). Stored conversion rules from the taxonomy are the only correct approach.

## Acceptance criteria

1. **Given** a raw `BiomarkerCandidate` with `original_unit="mmol/mol"` and `vitalog_id="hba1c"`, **When** conversion runs, **Then** `canonical_value` and `canonical_unit="%"` are computed using the IFCC formula stored in the taxonomy entry's `unit_conversions`.
2. **Given** a raw unit already in the canonical unit, **When** conversion runs, **Then** `canonical_value = original_value` and `canonical_unit = original_unit`.
3. **Given** a raw unit not in the taxonomy's `unit_conversions` for the resolved biomarker, **When** conversion runs, **Then** a `UnitConversionError` is raised and the record is flagged for review (does NOT proceed to auto-accept).
4. **Given** a converted value, **When** range validation runs, **Then** the value is checked against `physiological_min` and `physiological_max` in the taxonomy entry; out-of-range values are flagged (`verified_by="pending_user"`) but NOT discarded.
5. **Given** a value-with-no-unit case (parser found a number but no unit string), **When** the converter runs, **Then** the function returns `UnitMissing` and the record is flagged for review.
6. **Given** the contract, **When** I read `src/normalization/unit_converter.py`, **Then** zero LLM calls happen in this path (P4).

## Files to create / modify

- `src/normalization/unit_converter.py`
- `src/normalization/range_validator.py`
- `src/normalization/errors.py` — add `UnitConversionError`, `UnitMissing`
- `reference_data/biomarker_taxonomy.json` — ensure every entry has `unit_conversions` + `physiological_min` + `physiological_max` (extend A2 contract if needed)
- `tests/normalization/test_unit_converter.py`
- `tests/normalization/test_range_validator.py`

## Implementation notes

- Conversion rules are stored per-taxonomy-entry because the same unit pair can have different conversion factors for different biomarkers (e.g., `mg/dL ↔ mmol/L` differs between glucose and cholesterol).
- For HbA1c specifically: `%` ↔ `mmol/mol` follows the IFCC formula `HbA1c[%] = 0.0915 × HbA1c[mmol/mol] + 2.15`. Document the citation in the taxonomy entry's `provenance`.
- Conversion rules use a simple `{factor, offset}` shape: `canonical = factor * raw + offset`. Sufficient for capstone's 30 biomarkers.
- Physiological ranges are wider than guideline ranges. Example: HbA1c physiological [3.0, 18.0]%, guideline normal <5.7%, target for diabetics <7.0%. Out-of-physiological-range is "this is almost certainly a parser error"; out-of-guideline-range is "this is medically notable" (the latter is for trends, not the validator).
- The unit converter is the first place a numeric is parsed from the raw string. Robust parsing of "6.8%", "6.8 %", "<5.7", "120/80" — including range strings — lives here.
- For ranges like `<5.7`, the canonical value is the boundary; `range_qualifier="lt"` is stored separately. Don't lose the qualifier.

## Verification

- `pytest tests/normalization/test_unit_converter.py -q` — covers HbA1c %, mmol/mol; glucose mg/dL ↔ mmol/L; cholesterol mg/dL ↔ mmol/L
- `pytest tests/normalization/test_range_validator.py -q` — covers in-range, out-of-physiological, out-of-guideline (which should NOT flag)
- Manual: ingest the adversarial doc using mmol/mol for HbA1c, confirm it renders in the same trend chart as %-unit records

## INVEST check

- [x] Independent — A2 + E1 required
- [x] Negotiable — exact range bounds flexible (cite a source per biomarker)
- [x] Valuable — gates the hero chart
- [x] Estimable — well-bounded
- [x] Small — 3 pts
- [x] Testable — exhaustive unit-pair coverage

## Deferred (explicitly out of this story)

- Non-linear conversions (none of the 30 biomarkers need them at capstone scale)
- Compound units (e.g., `count × 10^9 / L`) — handled inline; full compound parser is v1+
- LLM-assisted unit normalization for novel units — v1+

## Notes / changelog

_(append after work is done)_
