"""Query-to-retrieval-set resolver for the NLQ Handler (F3).

Zero LLM calls. Pure deterministic: alias index lookup + condition group expansion.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow
from src.reference_data import load_biomarker_groups, load_taxonomy, lookup_alias

_ACCEPTED_VERIFIED_BY = frozenset({"auto", "user", "admin"})


@dataclass
class ResolveResult:
    """Result of a query resolution."""

    retrieval_set: dict[uuid.UUID, BiomarkerRecordRow]
    missing_canonical_ids: list[str]
    matched_condition_names: list[str] = field(default_factory=list)


def resolve_query(
    query: str,
    patient_id: uuid.UUID,
    repo: BiomarkerRepository,
) -> ResolveResult:
    """Parse query, fetch matching records, return ResolveResult.

    retrieval_set: accepted records for recognized biomarkers.
    missing_canonical_ids: recognized biomarker IDs with no accepted records for this patient.
    matched_condition_names: display names of conditions expanded via biomarker_groups.
    All empty means the query contained no recognized biomarker or condition references.
    """
    canonical_ids, matched_condition_names = _extract_canonical_ids(query)

    retrieval_set: dict[uuid.UUID, BiomarkerRecordRow] = {}
    missing: list[str] = []

    for cid in canonical_ids:
        records = repo.find_by_canonical_id(patient_id, cid)
        accepted = [
            r
            for r in records
            if r.canonical_value is not None
            and r.collection_date is not None
            and r.verified_by in _ACCEPTED_VERIFIED_BY
        ]
        if accepted:
            for r in accepted:
                retrieval_set[r.record_id] = r
        else:
            missing.append(cid)

    return ResolveResult(
        retrieval_set=retrieval_set,
        missing_canonical_ids=missing,
        matched_condition_names=matched_condition_names,
    )


def canonical_name(vitalog_id: str) -> str:
    """Return the canonical_name for a vitalog_id from the taxonomy, or vitalog_id if not found."""
    for entry in load_taxonomy():
        if entry["vitalog_id"] == vitalog_id:
            name: str = entry["canonical_name"]
            return name
    return vitalog_id


def _extract_canonical_ids(query: str) -> tuple[list[str], list[str]]:
    """Combine alias and condition group matches, deduplicating while preserving order.

    Returns (canonical_ids, matched_condition_display_names).
    """
    alias_ids = _direct_alias_matches(query)
    group_ids, matched_names = _condition_group_matches(query)

    seen: set[str] = set()
    result: list[str] = []
    for cid in alias_ids + group_ids:
        if cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result, matched_names


def _direct_alias_matches(query: str) -> list[str]:
    """Try trigrams → bigrams → unigrams against the taxonomy alias index.

    Strips trailing/leading punctuation from each token so "HbA1c?" resolves correctly.
    """
    raw_tokens = query.lower().split()
    tokens = [re.sub(r"[^a-z0-9_]", "", t) for t in raw_tokens]
    tokens = [t for t in tokens if t]
    found: list[str] = []
    seen: set[str] = set()
    for n in (3, 2, 1):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n])
            cid = lookup_alias(phrase)
            if cid and cid not in seen:
                found.append(cid)
                seen.add(cid)
    return found


_MIN_CONDITION_WORD_LEN = 8  # skip short words like "type", "1", "chronic", "disease"


def _condition_group_matches(query: str) -> tuple[list[str], list[str]]:
    """Expand condition keyword mentions to biomarker IDs using biomarker_groups.json.

    Matches on: condition key, full display name, or any significant word (>=8 chars)
    from the display name — so "diabetes" matches T2D without requiring the full
    "Type 2 Diabetes" string.

    Returns (found_biomarker_ids, matched_condition_display_names).
    The caller should include the display names in any response to clarify the grouping basis.
    """
    groups: dict[str, Any] = load_biomarker_groups()
    conditions: dict[str, Any] = groups.get("conditions", {})
    query_lower = query.lower()
    found: list[str] = []
    matched_names: list[str] = []
    seen_ids: set[str] = set()
    for cond_key, cond_data in conditions.items():
        display = str(cond_data.get("display_name", "")).lower()
        matched = (
            cond_key.lower() in query_lower
            or display in query_lower
            or any(
                word in query_lower
                for word in display.split()
                if len(word) >= _MIN_CONDITION_WORD_LEN
            )
        )
        if matched:
            matched_names.append(str(cond_data.get("display_name", cond_key)))
            for cid in cond_data.get("biomarkers", []):
                if cid not in seen_ids:
                    found.append(cid)
                    seen_ids.add(cid)
    return found, matched_names
