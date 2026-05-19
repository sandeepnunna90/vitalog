"""Unit tests for the C3 harness — comparator and aggregator logic.

All tests are pure logic; no network calls, no Textract, no Anthropic.
"""

from __future__ import annotations

import pytest

from src.eval.harness.aggregator import DocResult, aggregate
from src.eval.harness.comparator import DocComparison, compare_doc
from src.ingestion.structurer_schemas import Band, BiomarkerCandidate

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _cand(
    name: str = "HbA1c",
    value: str = "6.5",
    unit: str = "%",
    ref_range: str = "4.0-5.6%",
    date: str = "2024-01-01",
    band: Band = Band.AUTO_ACCEPT,
) -> BiomarkerCandidate:
    return BiomarkerCandidate(
        raw_name=name,
        raw_value=value,
        raw_unit=unit,
        raw_reference_range=ref_range,
        collection_date=date,
        lab_source="Quest Diagnostics",
        llm_confidence=99.0,
        source_page=1,
        composite_confidence=99.0,
        band=band,
    )


def _gt(
    vitalog_id: str = "hba1c",
    name: str = "HbA1c",
    value: str = "6.5",
    unit: str = "%",
    ref_range: str = "4.0-5.6%",
    date: str = "2024-01-01",
) -> dict[str, str]:
    return {
        "vitalog_id": vitalog_id,
        "original_name": name,
        "original_value": value,
        "original_unit": unit,
        "original_range": ref_range,
        "collection_date": date,
        "lab_source": "Quest Diagnostics",
    }


def _empty_comparison() -> DocComparison:
    return DocComparison(
        biomarker_matches=[],
        extra_extracted=0,
        band_distribution={},
        unmatched_extracted_composites=[],
    )


def _doc_result(comparison: DocComparison) -> DocResult:
    return DocResult(
        filename="test.pdf",
        split="synthetic",
        vendor="quest",
        expected_classification="lab_report",
        actual_classification="lab_report",
        classification_correct=True,
        comparison=comparison,
    )


# ── Comparator tests ──────────────────────────────────────────────────────────


def test_exact_match_all_fields_true() -> None:
    cmp = compare_doc([_cand()], [_gt()])
    assert len(cmp.biomarker_matches) == 1
    bm = cmp.biomarker_matches[0]
    assert bm.matched is True
    assert all(fr.match for fr in bm.fields)
    assert cmp.extra_extracted == 0
    assert bm.matched_composite_confidence == 99.0
    assert cmp.unmatched_extracted_composites == []


def test_value_decimal_within_tolerance() -> None:
    # 5.19 vs 5.2 → |0.01| / 5.2 ≈ 0.0019 < 0.005 → match
    cmp = compare_doc([_cand(value="5.19")], [_gt(value="5.2")])
    value_field = next(fr for fr in cmp.biomarker_matches[0].fields if fr.field == "value")
    assert value_field.match is True


def test_value_decimal_outside_tolerance() -> None:
    # 5.0 vs 5.2 → |0.2| / 5.2 ≈ 0.038 > 0.005 → no match
    cmp = compare_doc([_cand(value="5.0")], [_gt(value="5.2")])
    value_field = next(fr for fr in cmp.biomarker_matches[0].fields if fr.field == "value")
    assert value_field.match is False


def test_value_integer_exact_match() -> None:
    cmp = compare_doc([_cand(value="120")], [_gt(value="120")])
    value_field = next(fr for fr in cmp.biomarker_matches[0].fields if fr.field == "value")
    assert value_field.match is True


def test_value_integer_off_by_one() -> None:
    cmp = compare_doc([_cand(value="121")], [_gt(value="120")])
    value_field = next(fr for fr in cmp.biomarker_matches[0].fields if fr.field == "value")
    assert value_field.match is False


def test_name_fuzzy_match_above_threshold() -> None:
    # "Hemoglobin A1c" vs "HbA1c" — low ratio, won't match
    # Use a high-similarity pair instead: "Glucose, Fasting" vs "Glucose Fasting"
    cmp = compare_doc([_cand(name="Glucose Fasting")], [_gt(name="Glucose, Fasting")])
    bm = cmp.biomarker_matches[0]
    assert bm.matched is True
    assert bm.name_score >= 90.0


def test_name_below_threshold_unmatched() -> None:
    # Completely unrelated name — will not match
    cmp = compare_doc([_cand(name="Sodium")], [_gt(name="HbA1c")])
    bm = cmp.biomarker_matches[0]
    assert bm.matched is False
    assert bm.fields == []


def test_extra_extracted_counted() -> None:
    # 2 extracted, 1 GT → 1 match + 1 extra
    cands = [_cand(name="HbA1c"), _cand(name="Glucose, Fasting")]
    cmp = compare_doc(cands, [_gt(name="HbA1c")])
    assert cmp.extra_extracted == 1
    assert len(cmp.unmatched_extracted_composites) == 1
    assert cmp.unmatched_extracted_composites[0] == 99.0


def test_unmatched_gt_no_extracted() -> None:
    # 0 extracted, 1 GT → 0 matches (FN)
    cmp = compare_doc([], [_gt()])
    assert len(cmp.biomarker_matches) == 1
    assert cmp.biomarker_matches[0].matched is False
    assert cmp.extra_extracted == 0
    assert cmp.unmatched_extracted_composites == []
    assert cmp.biomarker_matches[0].matched_composite_confidence is None


# ── Aggregator tests ──────────────────────────────────────────────────────────


def test_aggregator_perfect_extraction() -> None:
    cmp = compare_doc([_cand()], [_gt()])
    report = aggregate([_doc_result(cmp)], run_id="test")
    for m in report.overall:
        assert m.tp == 1
        assert m.fp == 0
        assert m.fn == 0
        assert pytest.approx(m.f1, abs=1e-9) == 1.0


def test_aggregator_zero_extraction() -> None:
    # No extracted candidates → all FN
    cmp = compare_doc([], [_gt()])
    report = aggregate([_doc_result(cmp)], run_id="test")
    for m in report.overall:
        assert m.tp == 0
        assert m.fn == 1
        assert pytest.approx(m.f1, abs=1e-9) == 0.0


def test_aggregator_by_split_populated() -> None:
    cmp = compare_doc([_cand()], [_gt()])
    report = aggregate([_doc_result(cmp)], run_id="test")
    assert "synthetic" in report.by_split


def test_aggregator_by_band_populated() -> None:
    cmp = compare_doc([_cand(band=Band.AUTO_ACCEPT)], [_gt()])
    report = aggregate([_doc_result(cmp)], run_id="test")
    assert "auto_accept" in report.by_band
    for m in report.by_band["auto_accept"]:
        assert m.tp == 1
