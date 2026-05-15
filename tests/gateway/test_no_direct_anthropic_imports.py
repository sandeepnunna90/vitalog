"""AST walker — fails CI if any file outside src/gateway/ imports anthropic directly.

This enforces architecture principle P3: the Gateway is the single chokepoint
for all LLM calls. No other file may bypass it by importing anthropic directly.
"""

from __future__ import annotations

import ast
import pathlib


def test_no_direct_anthropic_imports() -> None:
    gateway_dir = pathlib.Path("src/gateway")
    violations: list[str] = []

    for path in sorted(pathlib.Path("src").rglob("*.py")):
        if path.is_relative_to(gateway_dir):
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if (alias.name or "").startswith("anthropic"):
                        violations.append(
                            f"{path}:{node.lineno} — "
                            f"'import {alias.name}' imports anthropic directly"
                        )
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").startswith("anthropic"):
                    violations.append(
                        f"{path}:{node.lineno} — "
                        f"'from {node.module} import ...' imports anthropic directly"
                    )

    assert not violations, (
        "Files outside src/gateway/ must not import anthropic directly.\n"
        "Use Gateway.call() instead.\n\n" + "\n".join(violations)
    )
