"""Layer 3 guardrails: deterministic banned-phrase scanner and schema validator.

Stack order (per architecture §7.2): schema → banned-phrase → citation (B4/B5).
If schema fails, downstream checks are skipped — output is rejected as a whole.

Phrases are loaded once at init from banned_phrases.txt; model never sees the list.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.gateway.errors import BannedPhraseViolation, SchemaValidationError

logger = logging.getLogger(__name__)

_T = TypeVar("_T", bound=BaseModel)

_DEFAULT_SHARED_DIR = Path(__file__).parent.parent.parent.parent / "prompts" / "_shared"


def _load_banned_phrases(shared_dir: Path) -> list[tuple[re.Pattern[str], str]]:
    """Return (compiled_pattern, original_phrase) tuples from banned_phrases.txt."""
    phrases_path = shared_dir / "banned_phrases.txt"
    if not phrases_path.exists():
        logger.warning("banned_phrases.txt not found at %s; L3 phrase scan disabled", phrases_path)
        return []
    entries: list[tuple[re.Pattern[str], str]] = []
    for line in phrases_path.read_text(encoding="utf-8").splitlines():
        phrase = line.strip()
        if phrase:
            entries.append((re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE), phrase))
    return entries


def _collect_output_text(raw: dict[str, Any]) -> str:
    parts: list[str] = []
    for value in raw.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            parts.append(_collect_output_text(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(_collect_output_text(item))
    return " ".join(parts)


class Layer3:
    def __init__(self, prompts_dir: Path | None = None) -> None:
        shared_dir = (prompts_dir / "_shared") if prompts_dir else _DEFAULT_SHARED_DIR
        self._phrases: list[tuple[re.Pattern[str], str]] = _load_banned_phrases(shared_dir)

    def validate_output(self, raw: dict[str, Any], output_schema: type[_T]) -> _T:
        """Run L3 validation: schema check first, then banned-phrase scan.

        Raises SchemaValidationError if Pydantic validation fails.
        Raises BannedPhraseViolation if any banned phrase appears in string output values.
        """
        try:
            validated = output_schema.model_validate(raw)
        except ValidationError as exc:
            raise SchemaValidationError(exc.errors()) from exc

        text = _collect_output_text(raw)
        hits = [phrase for pattern, phrase in self._phrases if pattern.search(text)]
        if hits:
            raise BannedPhraseViolation(phrases=hits)

        return validated
