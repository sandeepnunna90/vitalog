"""Query-to-retrieval-set resolver for the NLQ Handler (F3).

Zero LLM calls. Pure deterministic: alias index lookup + condition keyword expansion.
"""

from __future__ import annotations

import re
import uuid

from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.models import BiomarkerRecordRow
from src.reference_data import load_condition_biomarker_map, load_taxonomy, lookup_alias

_ACCEPTED_VERIFIED_BY = frozenset({"auto", "user", "admin"})


def resolve_query(
    query: str,
    patient_id: uuid.UUID,
    repo: BiomarkerRepository,
) -> tuple[dict[uuid.UUID, BiomarkerRecordRow], list[str]]:
    """Parse query, fetch matching records, return (retrieval_set, missing_canonical_ids).

    retrieval_set: accepted records for recognized biomarkers.
    missing_canonical_ids: recognized biomarker IDs that have no accepted records for this patient.
    Both empty means the query contained no recognized biomarker or condition references.
    """
    canonical_ids = _extract_canonical_ids(query)

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

    return retrieval_set, missing


def canonical_name(vitalog_id: str) -> str:
    """Return the canonical_name for a vitalog_id from the taxonomy, or vitalog_id if not found."""
    for entry in load_taxonomy():
        if entry["vitalog_id"] == vitalog_id:
            name: str = entry["canonical_name"]
            return name
    return vitalog_id


def _extract_canonical_ids(query: str) -> list[str]:
    """Combine alias and condition matches, deduplicating while preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for cid in _direct_alias_matches(query) + _condition_biomarker_matches(query):
        if cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result


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


def _condition_biomarker_matches(query: str) -> list[str]:
    """Expand condition keyword mentions to primary biomarker IDs.

    Matches on: condition key, full display name, or any significant word (>=8 chars)
    from the display name — so "diabetes" matches T2D without requiring the full
    "Type 2 Diabetes" string.
    """
    cond_map = load_condition_biomarker_map()
    conditions: dict[str, dict[str, list[str]]] = cond_map.get("conditions", {})
    query_lower = query.lower()
    found: list[str] = []
    seen: set[str] = set()
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
            for cid in cond_data.get("primary_biomarkers", []):
                if cid not in seen:
                    found.append(cid)
                    seen.add(cid)
    return found
