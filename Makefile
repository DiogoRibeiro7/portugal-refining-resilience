.PHONY: install test lint format check notebooks report-inputs report-pdf article-pdf clean

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

report-pdf:
	latexmk -pdf -interaction=nonstopmode -halt-on-error -cd reports/report_final.tex

article-pdf:
	latexmk -pdf -bibtex -interaction=nonstopmode -halt-on-error -cd reports/article.tex

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .ipynb_checkpoints -prune -exec rm -rf {} +
	latexmk -C -cd reports/report_final.tex
