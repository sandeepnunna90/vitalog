"""Root pytest configuration — loads .env so integration tests get credentials."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root (parent of tests/) before any test module is imported.
# This makes ANTHROPIC_API_KEY, SUPABASE_URL, etc. available to integration tests
# without requiring callers to export them manually.
load_dotenv(Path(__file__).parent.parent / ".env")
