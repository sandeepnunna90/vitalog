"""Per-field comparison between extracted BiomarkerCandidates and ground truth.

Tolerances mirror Mode B (citation_verifier_mode_b.py):
  - Decimal values: ±0.5%  (DECIMAL_TOLERANCE = 0.005)
  - Integer values: exact match
  - Name: rapidfuzz.fuzz.ratio >= NAME_FUZZY_THRESHOLD (90.0)
  - Unit, range, date: exact stripped string match
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from src.ingestion.structurer_schemas import BiomarkerCandidate

NAME_FUZZY_THRESHOLD: float = 90.0
DECIMAL_TOLERANCE: float = 0.005  # ±0.5%

FIELDS: tuple[str, ...] = ("name", "value", "unit", "range", "date")


@dataclass
class FieldResult:
    field: str  # one of FIELDS
    extracted: str
    expected: str
    match: bool


@dataclass
class BiomarkerMatch:
    """Comparison result for one GT biomarker entry."""

    vitalog_id: str
    name_score: float  # rapidfuzz ratio 0–100
    matched: bool  # True iff name_score >= NAME_FUZZY_THRESHOLD
    matched_band: str | None  # band.value of the matched extracted candidate; None if unmatched
    fields: list[FieldResult] = field(default_factory=list)  # populated only when matched=True
    matched_composite_confidence: float | None = None  # composite_confidence of matched candidate


@dataclass
class DocComparison:
    biomarker_matches: list[BiomarkerMatch]  # one entry per GT biomarker
    extra_extracted: int  # extracted candidates with no GT match
    band_distribution: dict[str, int]  # band.value → count across all extracted candidates
    # composite_confidence scores of candidates with no GT match; used by C5 grid search
    unmatched_extracted_composites: list[float] = field(default_factory=list)


def compare_doc(
    extracted: list[BiomarkerCandidate],
    ground_truth_biomarkers: list[dict[str, str]],
) -> DocComparison:
    """Compare extracted candidates against GT biomarkers for one document.

    Matching is greedy: each extracted candidate is consumed by at most one GT entry,
    chosen by highest rapidfuzz.fuzz.ratio score.
    """
    band_dist: dict[str, int] = {}
    for cand in extracted:
        band_dist[cand.band.value] = band_dist.get(cand.band.value, 0) + 1

    matched_indices: set[int] = set()
    matches: list[BiomarkerMatch] = []

    for gt in ground_truth_biomarkers:
        gt_name = gt.get("original_name", "")
        best_score = -1.0
        best_idx = -1

        for i, cand in enumerate(extracted):
            if i in matched_indices:
                continue
            score: float = fuzz.ratio(gt_name, cand.raw_name)
            if score > best_score:
                best_score = score
                best_idx = i

        if best_score >= NAME_FUZZY_THRESHOLD and best_idx >= 0:
            matched_indices.add(best_idx)
            cand = extracted[best_idx]
            matches.append(
                BiomarkerMatch(
                    vitalog_id=gt.get("vitalog_id", ""),
                    name_score=best_score,
                    matched=True,
                    matched_band=cand.band.value,
                    fields=_compare_fields(cand, gt),
                    matched_composite_confidence=cand.composite_confidence,
                )
            )
        else:
            matches.append(
                BiomarkerMatch(
                    vitalog_id=gt.get("vitalog_id", ""),
                    name_score=max(best_score, 0.0),
                    matched=False,
                    matched_band=None,
                )
            )

    extra = len(extracted) - len(matched_indices)
    unmatched_composites = [
        extracted[i].composite_confidence for i in range(len(extracted)) if i not in matched_indices
    ]
    return DocComparison(
        biomarker_matches=matches,
        extra_extracted=max(extra, 0),
        band_distribution=band_dist,
        unmatched_extracted_composites=unmatched_composites,
    )


def _compare_fields(cand: BiomarkerCandidate, gt: dict[str, str]) -> list[FieldResult]:
    return [
        FieldResult(
            field="name",
            extracted=cand.raw_name,
            expected=gt.get("original_name", ""),
            match=True,  # name always True for matched pairs (score >= threshold)
        ),
        FieldResult(
            field="value",
            extracted=cand.raw_value,
            expected=gt.get("original_value", ""),
            match=_value_match(cand.raw_value, gt.get("original_value", "")),
        ),
        FieldResult(
            field="unit",
            extracted=cand.raw_unit,
            expected=gt.get("original_unit", ""),
            match=cand.raw_unit.strip() == gt.get("original_unit", "").strip(),
        ),
        FieldResult(
            field="range",
            extracted=cand.raw_reference_range,
            expected=gt.get("original_range", ""),
            match=cand.raw_reference_range.strip() == gt.get("original_range", "").strip(),
        ),
        FieldResult(
            field="date",
            extracted=cand.collection_date,
            expected=gt.get("collection_date", ""),
            match=cand.collection_date.strip() == gt.get("collection_date", "").strip(),
        ),
    ]


def _value_match(extracted: str, expected: str) -> bool:
    """True if extracted and expected represent the same numeric value within tolerance.

    Decimal presence (any '.' in either string) selects ±0.5% tolerance; otherwise exact.
    """
    # Assumes values do not use comma-thousands separators (e.g. "1,234" vs "1234"
    # would fall through to string comparison and mismatch). Ground-truth values
    # must be written without thousand separators.
    try:
        e_val = float(extracted.strip())
        g_val = float(expected.strip())
    except ValueError:
        return extracted.strip() == expected.strip()

    if "." in extracted or "." in expected:
        if g_val == 0.0:
            return e_val == 0.0
        return abs(e_val - g_val) / abs(g_val) <= DECIMAL_TOLERANCE
    return e_val == g_val
