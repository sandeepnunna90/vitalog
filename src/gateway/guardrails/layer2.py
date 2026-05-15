"""Layer 2 guardrails: shared safety preamble and few-shot refusal injector.

Loaded once at Gateway init time (disk reads are not per-call).
The preamble and refusals are prepended to every system prompt verbatim.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_SHARED_DIR = Path(__file__).parent.parent.parent.parent / "prompts" / "_shared"


def _load_preamble(shared_dir: Path) -> str:
    preamble_path = shared_dir / "safety_preamble.md"
    if not preamble_path.exists():
        logger.warning("Safety preamble not found at %s; L2 preamble will be empty", preamble_path)
        return ""
    return preamble_path.read_text(encoding="utf-8").strip()


def _load_refusals(shared_dir: Path) -> str:
    refusals_dir = shared_dir / "few_shot_refusals"
    if not refusals_dir.exists():
        logger.warning(
            "Few-shot refusals dir not found at %s; L2 refusals will be empty",
            refusals_dir,
        )
        return ""
    files = sorted(refusals_dir.glob("*.md"))
    if not files:
        return ""
    examples = [f.read_text(encoding="utf-8").strip() for f in files]
    header = "Examples of appropriate responses (follow this refusal style exactly):"
    return header + "\n\n" + "\n\n".join(examples)


class Layer2:
    def __init__(self, prompts_dir: Path | None = None) -> None:
        shared_dir = (prompts_dir / "_shared") if prompts_dir else _DEFAULT_SHARED_DIR
        self._preamble = _load_preamble(shared_dir)
        self._refusals = _load_refusals(shared_dir)

    def augment_system(self, system: str, injection_warning: str | None = None) -> str:
        """Prepend preamble, optional injection warning, and few-shot refusals to system."""
        parts: list[str] = []
        if injection_warning:
            parts.append(injection_warning)
        if self._preamble:
            parts.append(self._preamble)
        if self._refusals:
            parts.append(self._refusals)
        parts.append(system)
        return "\n\n".join(parts)

    # Expose for tests
    @property
    def preamble(self) -> str:
        return self._preamble

    @property
    def refusals(self) -> str:
        return self._refusals
