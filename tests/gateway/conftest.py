"""Shared fixtures for gateway test suite."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture()
def prompts_dir(tmp_path: Path) -> Path:
    """Minimal prompt registry with a 'hello@v1' prompt using {name} variable."""
    registry = tmp_path / "_registry.yaml"
    registry.write_text(
        textwrap.dedent("""\
            prompts:
              - prompt_id: hello
                version: v1
                path: hello/v1.md
        """),
        encoding="utf-8",
    )
    (tmp_path / "hello").mkdir()
    (tmp_path / "hello" / "v1.md").write_text(
        textwrap.dedent("""\
            ---
            prompt_id: hello
            version: v1
            model: claude-sonnet-4-6
            max_tokens: 256
            system_template: "You are a helpful assistant."
            user_template: "Say hello to {name}."
            ---
        """),
        encoding="utf-8",
    )
    return tmp_path
