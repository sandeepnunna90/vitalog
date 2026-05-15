"""Supabase Storage adapter for raw document files.

Storage URIs:
  supabase-storage://<bucket>/<path>  — file is stored in Supabase Storage
  discard://<uuid>                    — file was intentionally not stored
                                        (retention_policy = 'discard_after_classification')
"""

from __future__ import annotations

import uuid

from supabase import Client

from src.persistence.models import RetentionPolicy

_BUCKET = "lab-reports"
_SUPABASE_SCHEME = "supabase-storage"
_DISCARD_SCHEME = "discard"


def _parse_uri(storage_uri: str) -> tuple[str, str]:
    """Return (scheme, path) from a storage URI."""
    scheme, _, rest = storage_uri.partition("://")
    return scheme, rest


class DocumentStore:
    def __init__(self, client: Client) -> None:
        self._client = client

    def put(
        self,
        file_bytes: bytes,
        filename: str,
        patient_id: uuid.UUID,
        retention_policy: RetentionPolicy,
    ) -> str:
        """Store a file and return its storage URI.

        For 'discard_after_classification' policies the file is not uploaded;
        a discard:// URI is returned so callers can record the audit entry
        without retaining the file content.
        """
        if retention_policy == "discard_after_classification":
            return f"{_DISCARD_SCHEME}://{uuid.uuid4()}"

        path = f"{patient_id}/{uuid.uuid4()}_{filename}"
        self._client.storage.from_(_BUCKET).upload(
            path=path,
            file=file_bytes,
            file_options={"content-type": "application/octet-stream"},
        )
        return f"{_SUPABASE_SCHEME}://{_BUCKET}/{path}"

    def get(self, storage_uri: str) -> bytes | None:
        """Download and return file bytes, or None for discard:// URIs."""
        scheme, path = _parse_uri(storage_uri)
        if scheme == _DISCARD_SCHEME:
            return None

        bucket, _, object_path = path.partition("/")
        response: bytes = self._client.storage.from_(bucket).download(object_path)
        return response
