#!/usr/bin/env python3
"""CLI for generating synthetic lab report PDFs.

Example:
    python scripts/generate_synthetic.py --vendor quest --count 5 --seed 42 --out /tmp/out/
    python scripts/generate_synthetic.py --vendor hospital --count 3 --seed 300 --out /tmp/out/
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.eval.synthesis.vendor_templates.hospital import generate_report as hospital_report
from src.eval.synthesis.vendor_templates.labcorp import generate_report as labcorp_report
from src.eval.synthesis.vendor_templates.quest import generate_report as quest_report

_VENDORS = {
    "quest": quest_report,
    "labcorp": labcorp_report,
    "hospital": hospital_report,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic lab report PDFs.")
    parser.add_argument("--vendor", required=True, choices=list(_VENDORS))
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    generate_fn = _VENDORS[args.vendor]
    for i in range(args.count):
        doc_seed = args.seed + i
        pdf, gt = generate_fn(doc_seed, args.out)
        print(f"  {pdf.name}  +  {gt.name}")


if __name__ == "__main__":
    main()
