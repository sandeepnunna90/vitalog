.PHONY: lint format typecheck test calibrate eval

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

typecheck:
	mypy --strict src/

test:
	pytest -q -m "not integration"; e=$$?; [ $$e -eq 0 ] || [ $$e -eq 5 ]

calibrate:
	@echo "Calibration not yet implemented (story C5)" && exit 1

eval:
	pytest -q tests/eval/
