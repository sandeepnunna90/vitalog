"""Eval logger — writes one JSONL entry per Gateway call.

Output path: eval_corpus/runs/<YYYY-MM-DD>/<run_id>.jsonl

Runs offline (no DB connection required). The eval pipeline reads these files
for extraction accuracy measurement and prompt regression detection.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src._paths import PROJECT_ROOT

_DEFAULT_RUNS_DIR = PROJECT_ROOT / "eval_corpus" / "runs"


@dataclass
class EvalLogEntry:
    run_id: str
    prompt_id: str
    version: str
    model: str
    inputs_redacted: dict[str, Any]  # B2 adds real PII redaction; B1 passes inputs through
    output: dict[str, Any] | None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    success: bool
    error: str | None
    timestamp: str  # ISO 8601 UTC
    session_id: str | None = None  # caller-supplied correlation ID across multiple gateway calls


def make_entry(
    *,
    prompt_id: str,
    version: str,
    model: str,
    inputs_redacted: dict[str, Any],
    output: dict[str, Any] | None,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    success: bool,
    error: str | None,
    session_id: str | None = None,
) -> EvalLogEntry:
    return EvalLogEntry(
        run_id=str(uuid.uuid4()),
        prompt_id=prompt_id,
        version=version,
        model=model,
        inputs_redacted=inputs_redacted,
        output=output,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        success=success,
        error=error,
        timestamp=datetime.now(UTC).isoformat(),
        session_id=session_id,
    )


class EvalLogger:
    def __init__(self, runs_dir: Path | None = None) -> None:
        self._runs_dir = runs_dir or _DEFAULT_RUNS_DIR

    def log(self, entry: EvalLogEntry) -> None:
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        day_dir = self._runs_dir / date_str
        day_dir.mkdir(parents=True, exist_ok=True)

        # One file per call (not a multi-entry JSONL). Each call is independently
        # addressable via run_id; session_id can correlate calls from the same operation.
        log_path = day_dir / f"{entry.run_id}.jsonl"
        with log_path.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(entry)) + "\n")
