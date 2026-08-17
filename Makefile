.PHONY: install test lint format check notebooks report-inputs clean

install:
	poetry install

test:
	poetry run pytest

lint:
	poetry run ruff check src tests scripts
	poetry run mypy src

format:
	poetry run ruff format src tests scripts
	poetry run ruff check src tests scripts --fix

check:
	poetry run ruff format --check src tests scripts
	poetry run ruff check src tests scripts
	poetry run mypy src
	poetry run pytest

notebooks:
	poetry run python scripts/run_notebooks.py

report-inputs:
	poetry run jupyter execute notebooks/19_export_report_inputs.ipynb

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .ipynb_checkpoints -prune -exec rm -rf {} +
