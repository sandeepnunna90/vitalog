"""Append-only repository for the audit_log table.

INSERT is the only allowed operation. The DB trigger (migration 002) fills
prev_hash, payload_hash, and chain_hash automatically.
"""

from __future__ import annotations

from typing import Any

from supabase import Client

from src.persistence.models import AuditLogCreate, AuditLogRow

_TABLE = "audit_log"


class AuditLogRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def record(self, actor: str, event_type: str, payload: dict[str, Any]) -> AuditLogRow:
        """Append an audit event. Hash columns are computed by the DB trigger."""
        entry = AuditLogCreate(actor=actor, event_type=event_type, payload=payload)
        data: Any = self._client.table(_TABLE).insert(entry.model_dump(mode="json")).execute().data
        return AuditLogRow.model_validate(data[0])

    def get_last_n(self, n: int = 10) -> list[AuditLogRow]:
        """Return the n most recent audit log rows (for hash chain verification)."""
        data: Any = (
            self._client.table(_TABLE)
            .select("*")
            .order("log_id", desc=True)
            .limit(n)
            .execute()
            .data
        )
        return [AuditLogRow.model_validate(row) for row in reversed(data)]
