.PHONY: setup lint format typecheck test migrate calibrate eval pre-demo-check

setup:
	uv sync --group dev
	git config core.hooksPath .githooks

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

typecheck:
	mypy --strict src/

test:
	pytest -q -m "not integration"; e=$$?; [ $$e -eq 0 ] || [ $$e -eq 5 ]

migrate:
	psql "$(SUPABASE_DB_URL)" -f migrations/001_initial_schema.sql
	psql "$(SUPABASE_DB_URL)" -f migrations/002_audit_log_hash_chain.sql

calibrate:
	@echo "Calibration not yet implemented (story C5)" && exit 1

eval:
	pytest -q tests/eval/

pre-demo-check:
	@echo "=== 1/2  Pending taxonomy queue ===" && \
	uv run python -c "
import os, sys
from supabase import create_client
from src.persistence.taxonomy_repository import TaxonomyRepository
client = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
pending = TaxonomyRepository(client).list_pending(status='pending')
if pending:
    print(f'FAIL: {len(pending)} unresolved pending entries'); sys.exit(1)
print('OK: queue is empty')
" && \
	echo "=== 2/2  Unit tests ===" && \
	uv run pytest -q -m "not integration" && \
	echo "" && echo "pre-demo-check PASSED"
