.PHONY: lint format typecheck test migrate calibrate eval

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
