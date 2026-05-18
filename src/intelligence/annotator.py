"""F6 SummaryAnnotator — persistence bridge and patient annotation for generated summaries."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from src.intelligence.export_schemas import Annotation
from src.intelligence.summary_schemas import Summary
from src.persistence.models import SummaryCreate, SummaryRow
from src.persistence.summary_repository import SummaryRepository

_VALID_SECTIONS = frozenset(
    {
        "conditions_section",
        "medications_section",
        "results_section",
        "trends_section",
        "data_gaps_section",
        "patient_notes",
    }
)

_audit_log = logging.getLogger("audit")


class SummaryAnnotator:
    def __init__(
        self,
        summary_repo: SummaryRepository,
        audit_repo: Any | None = None,
    ) -> None:
        self._repo = summary_repo
        self._audit = audit_repo

    def persist(self, summary: Summary) -> SummaryRow:
        """Persist an in-memory Summary to Supabase and return the row with its summary_id."""
        create = SummaryCreate(
            patient_id=summary.patient_id,
            content_json=summary.model_dump(mode="json"),
        )
        row = self._repo.add(create)
        _audit_log.info(
            "summary_persisted",
            extra={"patient_id": str(summary.patient_id), "summary_id": str(row.summary_id)},
        )
        if self._audit is not None:
            try:
                self._audit.record(
                    actor="system",
                    event_type="summary_persisted",
                    payload={
                        "patient_id": str(summary.patient_id),
                        "summary_id": str(row.summary_id),
                    },
                )
            except Exception as _exc:  # noqa: BLE001
                _audit_log.warning("audit_log_failed: %s", _exc)
        return row

    def add_note(self, summary_id: uuid.UUID, section: str, text: str) -> SummaryRow:
        """Append a patient annotation to a summary section.

        Raises ValueError if section is not a recognised field name or if
        the summary_id is not found.
        """
        if section not in _VALID_SECTIONS:
            raise ValueError(
                f"Invalid section: {section!r}. Valid sections: {sorted(_VALID_SECTIONS)}"
            )
        row = self._repo.get(summary_id)
        if row is None:
            raise ValueError(f"Summary {summary_id} not found")
        annotations = _parse_annotations(row.patient_annotations)
        annotations.append(
            Annotation(
                annotation_id=str(uuid.uuid4()),
                section=section,
                text=text,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        return self._repo.update_annotations(summary_id, _serialize_annotations(annotations))


# ── Module-level helpers ──────────────────────────────────────────────────────


def _parse_annotations(raw: str | None) -> list[Annotation]:
    if not raw:
        return []
    data = json.loads(raw)
    return [Annotation.model_validate(item) for item in data]


def _serialize_annotations(annotations: list[Annotation]) -> str:
    return json.dumps([a.model_dump(mode="json") for a in annotations], ensure_ascii=False)
