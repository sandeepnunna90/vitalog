"""LabCorp-style synthetic PDF renderer — template pending real report review.

The layout will be built after inspecting the user's real (redacted) LabCorp reports.
Until then this module raises NotImplementedError so the CLI fails gracefully.
"""

from __future__ import annotations

from pathlib import Path


def generate_report(
    seed: int,
    out_dir: Path,
    *,
    collection_date: str | None = None,
    lab_source: str = "Laboratory Corporation of America",
    overrides: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """LabCorp template — not yet implemented, pending real report layout review."""
    raise NotImplementedError(
        "LabCorp template is pending review of real LabCorp report layout. "
        "Use --vendor quest or --vendor hospital for now."
    )
