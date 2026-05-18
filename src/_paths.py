"""Central project-path constants.

Import from here instead of recomputing Path(__file__).parent chains in every module.
"""

from pathlib import Path

# Root of the repository (the directory that contains src/, prompts/, eval_corpus/, etc.)
PROJECT_ROOT: Path = Path(__file__).parent.parent
