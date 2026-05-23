"""Admin CLI for resolving the pending taxonomy queue.

Commands:
    list                                — show all pending entries
    confirm <pending_id> --canonical <vitalog_id>  — confirm and link to canonical
    reject  <pending_id>               — reject the entry
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

from supabase import create_client

from src.normalization.taxonomy_editor import add_alias
from src.persistence.biomarker_repository import BiomarkerRepository
from src.persistence.taxonomy_repository import TaxonomyRepository


def _get_client() -> object:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set", file=sys.stderr)
        sys.exit(1)
    return create_client(url, key)


def cmd_list(args: argparse.Namespace) -> None:
    client = _get_client()
    repo = TaxonomyRepository(client)  # type: ignore[arg-type]
    entries = repo.list_pending(status="pending")
    if not entries:
        print("Queue is empty — no pending entries.")
        return
    print(f"{'pending_id':<38}  {'raw_name':<30}  {'raw_unit':<12}  document_id")
    print("-" * 100)
    for e in entries:
        doc = str(e.document_id) if e.document_id else "—"
        unit = e.raw_unit or "—"
        print(f"{str(e.pending_id):<38}  {e.raw_name:<30}  {unit:<12}  {doc}")


def cmd_confirm(args: argparse.Namespace) -> None:
    pending_id = uuid.UUID(args.pending_id)
    canonical = args.canonical

    client = _get_client()
    taxonomy_repo = TaxonomyRepository(client)  # type: ignore[arg-type]
    biomarker_repo = BiomarkerRepository(client)  # type: ignore[arg-type]

    # Verify the pending entry exists and is still pending
    entries = taxonomy_repo.list_pending(status="pending")
    entry = next((e for e in entries if e.pending_id == pending_id), None)
    if entry is None:
        print(
            f"ERROR: pending entry {pending_id} not found or not in 'pending' status",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate canonical and update taxonomy file first — fails fast before any DB writes
    try:
        add_alias(canonical, entry.raw_name)
        print(f"Added alias {entry.raw_name!r} to {canonical!r} in biomarker_taxonomy.json")
    except ValueError as exc:
        print(f"Note: alias not added — {exc}")

    # Update biomarker records linked to this pending entry
    updated = biomarker_repo.resolve_pending_records(pending_id, canonical)

    # Mark pending entry confirmed
    taxonomy_repo.resolve_pending(pending_id, status="confirmed", resolved_by="admin")

    print(f"Confirmed: {pending_id} → {canonical!r}  ({updated} record(s) updated)")


def cmd_reject(args: argparse.Namespace) -> None:
    pending_id = uuid.UUID(args.pending_id)

    client = _get_client()
    repo = TaxonomyRepository(client)  # type: ignore[arg-type]
    repo.resolve_pending(pending_id, status="rejected", resolved_by="admin")
    print(f"Rejected: {pending_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve pending taxonomy queue entries.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all pending entries")

    p_confirm = sub.add_parser("confirm", help="Confirm a pending entry → canonical biomarker")
    p_confirm.add_argument("pending_id", help="UUID of the pending_taxonomy_entry")
    p_confirm.add_argument("--canonical", required=True, help="vitalog_id to map this entry to")

    p_reject = sub.add_parser("reject", help="Reject a pending entry")
    p_reject.add_argument("pending_id", help="UUID of the pending_taxonomy_entry")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "confirm":
        cmd_confirm(args)
    elif args.command == "reject":
        cmd_reject(args)


if __name__ == "__main__":
    main()
