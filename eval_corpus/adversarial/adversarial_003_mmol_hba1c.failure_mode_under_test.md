# Failure mode: non-standard HbA1c unit (mmol/mol)

HbA1c is reported as 48 mmol/mol (flag H) instead of the common % unit.

**Expected behaviour:** E3 unit conversion path converts 48 mmol/mol → ~6.5% before storing in `biomarker_records`. The stored `canonical_value` should be in %.
