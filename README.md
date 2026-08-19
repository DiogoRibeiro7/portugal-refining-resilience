# Portugal Refining Resilience

[![CI](https://github.com/DiogoRibeiro7/portugal-refining-resilience/actions/workflows/ci.yml/badge.svg)](https://github.com/DiogoRibeiro7/portugal-refining-resilience/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A notebook-first data-analysis repository studying how Portugal's petroleum-product system changed around two major refining events:

1. the Sines hydrocracker entering commercial production in **2013**, which materially increased diesel-producing capability; and
2. the discontinuation of refining at **Matosinhos in 2021**, which concentrated Portuguese refining at Sines.

The repository does **not** assume that refinery closure caused higher retail fuel prices. It separates and tests four mechanisms:

\[
\text{refining capability}
\rightarrow
\text{production / trade balance}
\rightarrow
\text{physical import dependence}
\rightarrow
\text{price co-movement and resilience}.
\]

The empirical question is:

> **Did the loss of refining capacity increase Portugal's dependence on imported finished petroleum products and reduce supply resilience, and did Portugal-Spain price co-movement change after the closure?**

## Repository status

This project is public research software. The committed code, notebooks, seed data, and
provenance files are structured for transparent review, but the empirical results should be
treated as work in progress until the acquisition notebooks have replaced or cross-validated
the provisional seed series.

## Quick start

Requirements:

- Python 3.11, 3.12, or 3.13
- Poetry 2.x
- Git

```bash
git clone git@github.com:DiogoRibeiro7/portugal-refining-resilience.git
cd portugal-refining-resilience
poetry install
poetry run pytest
```

Run the full local quality gate with:

```bash
make check
```

## Why notebooks are the main product

The analytical work lives in `notebooks/`. The `src/` package contains only reusable I/O, validation, source-adapter, metric, and statistical functions. Every major analytical decision should remain visible in the notebooks.

The notebook pipeline persists results at each stage:

```text
raw downloads
    ↓
data/interim/           source-specific normalised tables
    ↓
data/processed/         canonical analytical panels
    ↓
data/metrics/           scalar/model/event-study metrics
    ↓
figures/ + tables/      report-ready outputs
    ↓
artifacts/report_inputs/
```

## Notebook sequence

| # | Notebook | Main output |
|---:|---|---|
| 00 | `00_research_questions_and_design.ipynb` | estimands, hypotheses, causal guardrails |
| 01 | `01_source_audit_and_manifest.ipynb` | frozen source manifest |
| 02 | `02_acquire_dgeg_trade_and_sales.ipynb` | DGEG raw workbooks and canonical trade extraction |
| 03 | `03_acquire_jodi_oil.ipynb` | JODI secondary-products database |
| 04 | `04_acquire_eurostat_oil_balance.ipynb` | Eurostat PT/ES oil balance panel |
| 05 | `05_acquire_weekly_oil_prices.ipynb` | EC Weekly Oil Bulletin history |
| 06 | `06_refinery_events_and_capacity.ipynb` | event/capacity reference tables |
| 07 | `07_process_trade_data.ipynb` | annual diesel/gasoline trade |
| 08 | `08_process_domestic_demand.ipynb` | annual domestic demand/sales |
| 09 | `09_process_refinery_output.ipynb` | annual refinery output / system regime |
| 10 | `10_build_analytical_panel.ipynb` | canonical annual and monthly fuel panels |
| 11 | `11_descriptive_trade_and_supply.ipynb` | long-run descriptive figures/metrics |
| 12 | `12_import_dependence_and_refinery_output_ratio.ipynb` | dependency and refinery-output ratios |
| 13 | `13_structural_breaks.ipynb` | event-aligned break tests |
| 14a | `14_2022_stress_test.ipynb` | 2022 stress metrics |
| 14b | `14_monthly_event_analysis.ipynb` | monthly event-timing models |
| 15 | `15_price_comovement.ipynb` | PT-ES price co-movement models |
| 16 | `16_spain_comparison.ipynb` | PT-ES price spreads and physical-balance comparisons |
| 17 | `17_robustness_and_sensitivity.ipynb` | alternative definitions and windows |
| 18 | `18_final_tables_figures_metrics.ipynb` | report-ready outputs |
| 19 | `19_export_report_inputs.ipynb` | compact evidence bundle |
| 20 | `20_report_readiness_check.ipynb` | completeness / claim audit |

## Core data sources

The primary design uses multiple independent sources instead of trusting a single series:

- **DGEG**: Portuguese petroleum-product imports/exports, annual sales, energy balances and fuel-price statistics.
- **JODI Oil World Database**: monthly secondary-product imports, exports, refinery output and demand; useful for transparent time aggregation and cross-checks.
- **Eurostat `nrg_cb_oil`**: annual oil supply, transformation and consumption for Portugal and Spain.
- **European Commission Weekly Oil Bulletin**: weekly consumer prices with and without taxes from 2005 onward.
- **Galp official disclosures**: dated refinery events used only as event metadata, not as outcome data.

See `config/sources.yml` and `data/reference/refinery_events.csv`.

## Stored data and metrics

This repository intentionally stores transformed outputs. Do not make the final report depend on notebook display state.

- `data/interim/`: source-normalised observations.
- `data/processed/`: canonical panels that can be reviewed independently of code.
- `data/metrics/`: descriptive, structural-break, stress-test, price co-movement, and robustness metrics.
- `data/provenance/`: source snapshots, hashes, extraction timestamps and processing metadata.
- `artifacts/report_inputs/`: only the files the report-writing prompts are allowed to treat as empirical evidence.

CSV is always written for human inspection. Parquet is written where available for typed reuse.

Raw downloaded files are excluded from version control by default because they can be large or
license-sensitive. The downloader refuses to overwrite an existing raw file unless a new source
vintage is requested explicitly, and writes metadata sidecars with retrieval time, URL, SHA-256 and
snapshot status. Commit transformed datasets only when they are intentionally part of the
reviewable analysis surface.

The report's tables and figures are mapped to their sources in
[reports/data_provenance.md](reports/data_provenance.md), which records where each one
comes from and which notebook produced it.

Report writing is driven by prompts kept outside version control. Whatever drives it must use
the checksum-protected `artifacts/report_inputs/` bundle rather than notebook display state or
chat history, which is why the bundle carries a manifest that accounts for every file in it.

Monthly event-timing claims must use `data/processed/fuel_monthly_analytical_panel.csv` and
the persisted `data/metrics/monthly_event_models.csv` / `monthly_event_phase_summary.csv`
outputs, which separate the May 2021 Matosinhos transition from the March 2022 energy-stress
period with monthly seasonality controls.

Cross-source comparisons must pass the tested readiness checks in
`portugal_refining_resilience.readiness`; file existence alone is not enough. Product definitions
are audited through `data/reference/product_definition_crosswalk.csv` before DGEG/JODI/Eurostat
values are interpreted as comparable.

## Preliminary seed series

`data/processed/jodi_portugal_fuel_exports_2005_2024_seed.csv` contains the 20-year export series already pulled during the project scoping discussion. It exists so the descriptive notebooks have an auditable starting point. It is marked **seed / provisional** and should be replaced or cross-validated by the acquisition notebooks before publication.

## Main metrics

For fuel \(j\) in year \(t\):

\[
\text{NetImports}_{j,t}=M_{j,t}-X_{j,t}
\]

\[
\text{GrossImportDependence}_{j,t}=\frac{M_{j,t}}{D_{j,t}}
\]

\[
\text{NetImportToDemandRatio}_{j,t}=\frac{M_{j,t}-X_{j,t}}{D_{j,t}}
\]

\[
\text{RefineryOutputToDemandRatio}_{j,t}=\frac{Q^{refinery}_{j,t}}{D_{j,t}}
\]

where \(M\) is imports, \(X\) exports, \(D\) domestic demand/sales and \(Q^{refinery}\) refinery output.

The refinery-output-to-demand ratio is not interpreted as self-sufficiency: Portuguese
refinery output may be exported while Portugal imports a different product stream. Price
analysis is conducted primarily **before taxes**, with after-tax prices reported separately.
Spain is used as a comparison series, not automatically as a causal counterfactual. Weekly
price-level models require stationarity diagnostics, and persistent levels should be
interpreted as co-movement rather than causal international pass-through unless stronger
time-series evidence is added.

## Identification guardrails

The report must distinguish:

- a documented industrial event;
- a structural break in an outcome series;
- an association after an event; and
- a causal effect.

A break near 2021/2022 does not, by itself, prove the Matosinhos closure caused the change. COVID recovery, the invasion of Ukraine, Russian VGO disruption, Sines maintenance, demand changes and common European price shocks are competing explanations that must be modelled or discussed.

## Development

Install the development environment:

```bash
poetry install
poetry run pre-commit install
```

Useful commands:

```bash
make test       # run tests
make lint       # run Ruff and mypy
make format     # format code and apply safe Ruff fixes
make check      # run format check, lint, type check, and tests
make notebooks  # execute notebooks in sequence
```

Run notebooks individually while developing. The sequential runner is primarily for reproducibility checks.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow, notebook expectations,
and data provenance rules. Security-sensitive reports should follow [SECURITY.md](SECURITY.md).

## Citation

If you use this repository, cite it using the metadata in [CITATION.cff](CITATION.cff).

## License

Code and documentation are released under the [MIT License](LICENSE). Data files may be derived
from third-party public sources; check source-specific terms before reuse.
