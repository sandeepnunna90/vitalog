#!/usr/bin/env python3
"""Run the adversarial prompt suite against the NLQ handler.

Dry-run (no API calls — validates report shape, all prompts grade as safe):
    python scripts/run_adversarial.py --prompts tests/adversarial/prompts/ --dry-run

Live run (requires ANTHROPIC_API_KEY, makes one LLM call per prompt):
    python scripts/run_adversarial.py --prompts tests/adversarial/prompts/

Exit code: 0 if all prompts pass, 1 if any produce clinical_advice.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

_FIXED_PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_DRY_RUN_OUTPUT = (
    "Your HbA1c was recorded on the date shown. "
    "Please speak with your healthcare provider for clinical interpretation."
)


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _prompt_versions() -> dict[str, str]:
    prompts_dir = Path(__file__).parent.parent / "prompts"
    versions: dict[str, str] = {}
    if prompts_dir.exists():
        for md_file in sorted(prompts_dir.rglob("*.md")):
            parts = md_file.relative_to(prompts_dir).parts
            if len(parts) == 2:
                versions[parts[0]] = md_file.stem
    return versions


def _make_stub_record() -> object:
    """Return a minimal BiomarkerRecordRow for the stub repository."""
    from datetime import date
    from datetime import datetime as dt

    from src.persistence.models import BiomarkerRecordRow

    return BiomarkerRecordRow.model_validate(
        {
            "record_id": str(uuid.uuid4()),
            "patient_id": str(_FIXED_PATIENT_ID),
            "document_id": None,
            "canonical_biomarker_id": "hba1c",
            "pending_taxonomy_id": None,
            "original_name": "HbA1c",
            "original_value": "7.8",
            "original_unit": "%",
            "original_range": "4.0-5.6%",
            "canonical_value": 7.8,
            "canonical_unit": "%",
            "collection_date": str(date(2026, 3, 12)),
            "lab_source": "Quest Diagnostics",
            "extraction_confidence": 98.0,
            "verified_by": "auto",
            "created_at": str(dt(2026, 3, 12, 10, 0, 0)),
        }
    )


def _build_live_components() -> tuple[object, object]:
    """Return (gateway, nlq_handler) for a live run."""
    import os
    from unittest.mock import MagicMock

    from src.gateway.gateway import Gateway
    from src.intelligence.nlq_handler import NlqHandler
    from src.persistence.biomarker_repository import BiomarkerRepository

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    gateway = Gateway(api_key=api_key)

    stub_repo = MagicMock(spec=BiomarkerRepository)
    stub_record = _make_stub_record()
    stub_repo.find_by_canonical_id.return_value = [stub_record]
    stub_repo.find_by_patient_id.return_value = [stub_record]

    handler = NlqHandler(gateway, stub_repo)
    return gateway, handler


@dataclass
class AttackResult:
    filename: str
    category: str
    expected: str
    grade: str
    passed: bool
    reason: str
    output_text: str


def _run_one(
    spec: object,
    handler: object,
    grader: object,
    dry_run: bool,
) -> AttackResult:
    from src.eval.adversarial.grader import Grade, PromptSpec

    assert isinstance(spec, PromptSpec)

    if dry_run:
        grade_result = grader.grade(_DRY_RUN_OUTPUT)  # type: ignore[union-attr]
        return AttackResult(
            filename=spec.filename,
            category=spec.category,
            expected=spec.expected,
            grade=grade_result.grade.value,
            passed=True,
            reason=grade_result.reason,
            output_text=_DRY_RUN_OUTPUT,
        )

    try:
        response = handler.answer(query=spec.input_text, patient_id=_FIXED_PATIENT_ID)  # type: ignore[union-attr]
        output_text: str = response.text
        grade_result = grader.grade(output_text)  # type: ignore[union-attr]
    except Exception as exc:
        grade_result = grader.grade_exception(exc)  # type: ignore[union-attr]
        output_text = f"[exception: {type(exc).__name__}: {exc}]"

    passed = grade_result.grade != Grade.CLINICAL_ADVICE
    return AttackResult(
        filename=spec.filename,
        category=spec.category,
        expected=spec.expected,
        grade=grade_result.grade.value,
        passed=passed,
        reason=grade_result.reason,
        output_text=output_text[:200],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run adversarial prompt suite against the NLQ handler."
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        required=True,
        help="Directory containing adversarial prompt .md files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM calls; grade a safe fixed string for each prompt.",
    )
    args = parser.parse_args()

    from src.eval.adversarial.grader import AdversarialGrader, load_prompt_spec

    prompt_files = sorted(args.prompts.glob("*.md"))
    if not prompt_files:
        print(f"No prompt files found in {args.prompts}")
        sys.exit(1)

    specs = [load_prompt_spec(p) for p in prompt_files]

    if args.dry_run:
        grader = AdversarialGrader()
        handler = None
        gateway = None
    else:
        gateway, handler = _build_live_components()
        grader = AdversarialGrader(gateway=gateway)  # type: ignore[arg-type]

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"\n[{mode}] Running {len(specs)} adversarial prompts ...\n")

    results: list[AttackResult] = []
    for spec in specs:
        result = _run_one(spec, handler, grader, args.dry_run)
        results.append(result)
        status = "PASS" if result.passed else "FAIL"
        print(f"  {status}  {result.filename:<45} grade={result.grade:<16} reason={result.reason}")

    pass_count = sum(1 for r in results if r.passed)
    fail_count = len(results) - pass_count

    print(f"\n{'=' * 60}")
    print(f"Results: {pass_count}/{len(results)} passed, {fail_count} failed")

    # Append to results_history.jsonl
    history_path = Path(__file__).parent.parent / "tests" / "adversarial" / "results_history.jsonl"
    run_entry = {
        "timestamp": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "git_sha": _git_sha(),
        "dry_run": args.dry_run,
        "prompt_versions_json": json.dumps(_prompt_versions()),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "results": [asdict(r) for r in results],
    }
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(run_entry) + "\n")
    print(f"Run logged to: {history_path}")

    if fail_count > 0:
        print(
            "\n\033[91mROLLBACK REQUIRED: adversarial testing detected clinical advice output."
            " Prompt revision required before demo.\033[0m"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
