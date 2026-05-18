"""Prompt registry — loads versioned prompts from prompts/<concern>/<version>.md.

Each prompt file has YAML frontmatter (between --- delimiters) with fields:
  prompt_id, version, model (optional), max_tokens,
  system_template (optional), user_template.

The body after the closing --- is ignored (human documentation only).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.gateway.errors import PromptNotFoundError
from src.gateway.model_router import default_model

_DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


@dataclass(frozen=True)
class PromptTemplate:
    prompt_id: str
    version: str
    model: str
    max_tokens: int
    system_template: str
    user_template: str
    output_schema_name: str  # Pydantic class name declared in frontmatter (AC6)


def _parse_prompt_file(path: Path) -> PromptTemplate:
    """Parse a prompt markdown file and return a PromptTemplate."""
    text = path.read_text(encoding="utf-8")

    # Split on '---' delimiters; first segment is empty (before opening ---),
    # second is the frontmatter, rest is body (ignored).
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Prompt file {path} has malformed frontmatter (missing --- delimiters)")

    frontmatter_text = parts[1].strip()
    fm: dict[str, Any] = yaml.safe_load(frontmatter_text) or {}

    try:
        return PromptTemplate(
            prompt_id=str(fm["prompt_id"]),
            version=str(fm["version"]),
            model=str(fm.get("model") or default_model()),
            max_tokens=int(fm["max_tokens"]),
            system_template=str(fm.get("system_template") or ""),
            user_template=str(fm["user_template"]),
            output_schema_name=str(fm["output_schema_name"]),
        )
    except KeyError as exc:
        raise ValueError(f"Prompt file {path} missing required field: {exc}") from exc


class PromptRegistry:
    """Eagerly loads all registered prompts at construction time.

    Intentionally fails hard on missing registry file (unlike the audit log,
    which is a soft dependency). Missing prompts are a deploy error; missing
    audit log is a monitoring gap. The asymmetry is deliberate.
    """

    def __init__(self, prompts_dir: Path | None = None) -> None:
        root = prompts_dir or _DEFAULT_PROMPTS_DIR
        registry_path = root / "_registry.yaml"

        if not registry_path.exists():
            raise FileNotFoundError(f"Prompt registry not found: {registry_path}")

        raw: dict[str, Any] = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        entries: list[dict[str, Any]] = raw.get("prompts", [])

        # key: (prompt_id, version) → PromptTemplate
        self._store: dict[tuple[str, str], PromptTemplate] = {}

        for entry in entries:
            prompt_id = str(entry["prompt_id"])
            version = str(entry["version"])
            rel_path = str(entry["path"])
            file_path = root / rel_path

            if not file_path.exists():
                raise FileNotFoundError(
                    f"Prompt file referenced in registry not found: {file_path}"
                )

            tmpl = _parse_prompt_file(file_path)

            if tmpl.prompt_id != prompt_id or tmpl.version != version:
                raise ValueError(
                    f"Frontmatter mismatch in {file_path}: "
                    f"registry says ({prompt_id}, {version}), "
                    f"frontmatter says ({tmpl.prompt_id}, {tmpl.version})"
                )

            self._store[(prompt_id, version)] = tmpl

    def get(self, prompt_id: str, version: str) -> PromptTemplate:
        """Return the PromptTemplate or raise PromptNotFoundError."""
        key = (prompt_id, version)
        if key not in self._store:
            raise PromptNotFoundError(f"Prompt not found in registry: {prompt_id!r}@{version}")
        return self._store[key]
