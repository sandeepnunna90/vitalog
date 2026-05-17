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

## Implementation plan

### New files

**`src/normalization/errors.py`**
```python
class UnitConversionError(Exception):
    vitalog_id: str
    raw_unit: str

class UnitMissing(Exception):
    vitalog_id: str
```

**`src/normalization/unit_converter.py`**

Public API: `convert(vitalog_id, raw_value_str, raw_unit) → ConversionResult`

`ConversionResult` dataclass fields:
- `canonical_value: float`
- `canonical_unit: str`
- `range_qualifier: str` — `"eq"` | `"lt"` | `"lte"` | `"gt"` | `"gte"`

Logic:
1. `raw_unit` is None/empty → raise `UnitMissing`
2. Load taxonomy via `load_taxonomy()` (lru_cached); find entry by `vitalog_id` or raise `UnitConversionError`
3. Parse `raw_value_str` with `_parse_value()`: handles `<5.7`, `>=6.5`, plain `6.8`
4. If `raw_unit` matches `ucum_unit` (case-insensitive, stripped) → identity (no conversion)
5. Find matching rule in `entry["unit_conversions"]` where `from_unit` == `raw_unit`; if none → raise `UnitConversionError`
6. Apply formula:
   - `"linear"`: `canonical = rule["factor"] * raw`
   - `"ifcc_to_ngsp"`: `canonical = 0.0915 * raw + 2.15` (IFCC→NGSP, mmol/mol → %)
7. Return `ConversionResult`

**`src/normalization/range_validator.py`**

Public API: `validate_physiological_range(vitalog_id, canonical_value) → RangeValidationResult`

`RangeValidationResult` dataclass fields:
- `in_physiological_range: bool`
- `physiological_min: float`
- `physiological_max: float`

Logic: load taxonomy, find entry, compare `physiological_min <= canonical_value <= physiological_max`.

### Modified files

**`reference_data/biomarker_taxonomy.json`** — add `physiological_min` and `physiological_max` to all 30 entries:

| vitalog_id | phys_min | phys_max | unit |
|---|---|---|---|
| hba1c | 3.0 | 18.0 | % |
| fasting_glucose | 20.0 | 600.0 | mg/dL |
| postprandial_glucose | 50.0 | 600.0 | mg/dL |
| total_cholesterol | 50.0 | 500.0 | mg/dL |
| ldl_cholesterol | 10.0 | 400.0 | mg/dL |
| hdl_cholesterol | 5.0 | 150.0 | mg/dL |
| triglycerides | 20.0 | 2000.0 | mg/dL |
| non_hdl_cholesterol | 20.0 | 450.0 | mg/dL |
| egfr | 1.0 | 140.0 | mL/min/1.73m² |
| creatinine | 0.2 | 15.0 | mg/dL |
| urine_acr | 0.0 | 5000.0 | mg/g |
| bp_systolic | 50.0 | 250.0 | mmHg |
| bp_diastolic | 30.0 | 150.0 | mmHg |
| tsh | 0.001 | 100.0 | mIU/L |
| free_t4 | 0.1 | 6.0 | ng/dL |
| alt | 1.0 | 3000.0 | U/L |
| ast | 1.0 | 3000.0 | U/L |
| hs_crp | 0.0 | 200.0 | mg/L |
| vitamin_d | 4.0 | 150.0 | ng/mL |
| vitamin_b12 | 100.0 | 2000.0 | pg/mL |
| ferritin | 1.0 | 10000.0 | ng/mL |
| hemoglobin | 3.0 | 25.0 | g/dL |
| wbc | 0.1 | 100.0 | K/uL |
| platelets | 10.0 | 1500.0 | K/uL |
| sodium | 100.0 | 180.0 | mEq/L |
| potassium | 1.5 | 9.0 | mEq/L |
| chloride | 70.0 | 130.0 | mEq/L |
| bun | 1.0 | 200.0 | mg/dL |
| serum_glucose | 20.0 | 600.0 | mg/dL |
| fructosamine | 100.0 | 700.0 | umol/L |

### Tests

**`tests/normalization/test_unit_converter.py`** (~10 tests):
- `test_hba1c_mmol_mol_to_percent` — 48 mmol/mol → ≈6.54% (IFCC: 0.0915×48+2.15)
- `test_identity_no_conversion_needed` — HbA1c already in % → same value
- `test_glucose_mmol_l_to_mg_dl` — 5.5 mmol/L → 5.5×18.0182 ≈ 99.1 mg/dL
- `test_cholesterol_mmol_l_to_mg_dl` — cholesterol conversion
- `test_unknown_unit_raises` — raw_unit not in conversions → `UnitConversionError`
- `test_missing_unit_none_raises` — None → `UnitMissing`
- `test_missing_unit_empty_raises` — "" → `UnitMissing`
- `test_qualifier_lt_preserved` — "<5.7" → canonical_value=5.7, qualifier="lt"
- `test_qualifier_gte_preserved` — ">=6.5" → canonical_value=6.5, qualifier="gte"
- `test_unknown_vitalog_id_raises` — raises `UnitConversionError`

**`tests/normalization/test_range_validator.py`** (~6 tests):
- `test_in_range_returns_true` — HbA1c 6.5% in [3.0, 18.0] → True
- `test_below_min_returns_false` — HbA1c 1.0% → False
- `test_above_max_returns_false` — HbA1c 25.0% → False
- `test_boundary_min_included` — exactly 3.0 → True
- `test_boundary_max_included` — exactly 18.0 → True
- `test_unknown_vitalog_id_raises` — ValueError

### Verification
```bash
pytest tests/normalization/test_unit_converter.py -q
pytest tests/normalization/test_range_validator.py -q
make lint && make typecheck
```

## Notes / changelog

_(append after work is done)_
