# Contributing

This is a notebook-first research repository. Contributions should improve
reproducibility, source traceability, statistical clarity, or the reusable
Python helpers that support the notebooks.

## Local setup

```bash
poetry install
poetry run pre-commit install
```

Run the core checks before opening a pull request:

```bash
poetry run pytest
poetry run ruff format --check src tests scripts
poetry run ruff check src tests scripts
poetry run mypy src
```

## Notebook changes

- Keep major analytical decisions visible in notebooks.
- Prefer small, reviewable notebook diffs.
- Do not commit raw downloaded source files under `data/raw/`.
- Add or update provenance records when transformed data changes.
- Keep report claims aligned with committed tables, figures, metrics, and
  `artifacts/report_inputs/`.

## Data changes

Document each new or changed data source with:

- source name and URL or citation;
- retrieval date;
- coverage period;
- unit definitions;
- transformations applied;
- caveats or known breaks in coverage.

Raw files should be reproducible downloads. Commit transformed, reviewable
outputs only when they are intentionally part of the analysis surface.

## Code style

The reusable package in `src/` is intentionally small. Add helpers there when
logic is shared across notebooks or needs focused tests. Keep exploratory
analysis in notebooks.
