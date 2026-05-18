#!/usr/bin/env python3
"""Redact HIPAA Safe Harbor identifiers from a real lab report PDF using PyMuPDF.

Usage:
    python scripts/redact_real.py \\
        --input /path/to/original_report.pdf \\
        --output eval_corpus/redacted_real/report_001.pdf \\
        --terms "John Doe" "1975-03-15" "123456789" "Dr. Smith" "555-1234-56"

The --terms list should include every identifier you want blacked out:
  patient name, DOB, MRN, account number, accession number, ordering physician,
  NPI, phone/fax, email, address components (street, zip).

Each matching text occurrence is replaced with a black rectangle.
Run --dry-run first to see how many matches are found without writing output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF


def redact_pdf(
    input_path: Path,
    output_path: Path,
    terms: list[str],
    *,
    dry_run: bool = False,
) -> int:
    """Redact all occurrences of each term in input_path, write to output_path.

    Returns the total number of redaction annotations applied.
    """
    doc = fitz.open(str(input_path))
    total = 0

    for page in doc:
        for term in terms:
            if not term.strip():
                continue
            hits = page.search_for(term)
            for rect in hits:
                page.add_redact_annot(rect, fill=(0, 0, 0))
                total += 1

        if not dry_run:
            page.apply_redactions()

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))

    doc.close()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Redact HIPAA identifiers from a lab report PDF.")
    parser.add_argument("--input", type=Path, required=True, help="Original PDF path")
    parser.add_argument("--output", type=Path, required=True, help="Redacted PDF output path")
    parser.add_argument(
        "--terms",
        nargs="+",
        required=True,
        help="Text strings to redact (name, DOB, MRN, etc.)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count matches without writing output",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    count = redact_pdf(args.input, args.output, args.terms, dry_run=args.dry_run)

    if args.dry_run:
        print(f"Dry run: {count} redaction(s) would be applied.")
    else:
        print(f"Redacted {count} occurrence(s). Output written to: {args.output}")


if __name__ == "__main__":
    main()
