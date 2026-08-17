# Portugal Refining Resilience

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
\text{price transmission and resilience}.
\]

The empirical question is:

> **Did the loss of refining capacity increase Portugal's dependence on imported finished petroleum products and reduce supply resilience, and did international price transmission change after the closure?**

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
| 02 | `02_acquire_dgeg_trade_and_sales.ipynb` | DGEG raw workbooks |
| 03 | `03_acquire_jodi_oil.ipynb` | JODI secondary-products database |
| 04 | `04_acquire_eurostat_oil_balance.ipynb` | Eurostat PT/ES oil balance |
| 05 | `05_acquire_weekly_oil_prices.ipynb` | EC Weekly Oil Bulletin history |
| 06 | `06_refinery_events_and_capacity.ipynb` | event/capacity reference tables |
| 07 | `07_process_trade_data.ipynb` | annual diesel/gasoline trade |
| 08 | `08_process_domestic_demand.ipynb` | annual domestic demand/sales |
| 09 | `09_process_refinery_output.ipynb` | annual refinery output / system regime |
| 10 | `10_build_analytical_panel.ipynb` | canonical annual fuel panel |
| 11 | `11_descriptive_trade_and_supply.ipynb` | long-run descriptive figures/metrics |
| 12 | `12_import_dependence_and_self_sufficiency.ipynb` | dependency metrics |
| 13 | `13_structural_breaks.ipynb` | event-aligned break tests |
| 14 | `14_2022_stress_test.ipynb` | 2022 stress metrics |
| 15 | `15_price_pass_through.ipynb` | PT price transmission models |
| 16 | `16_spain_comparison.ipynb` | PT–ES spreads / controlled ITS |
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
- `data/metrics/`: descriptive, structural-break, stress-test, pass-through, and robustness metrics.
- `data/provenance/`: source snapshots, hashes, extraction timestamps and processing metadata.
- `artifacts/report_inputs/`: only the files the report-writing prompts are allowed to treat as empirical evidence.

CSV is always written for human inspection. Parquet is written where available for typed reuse.

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
\text{NetImportDependence}_{j,t}=\frac{M_{j,t}-X_{j,t}}{D_{j,t}}
\]

\[
\text{DomesticOutputCoverage}_{j,t}=\frac{Q^{refinery}_{j,t}}{D_{j,t}}
\]

where \(M\) is imports, \(X\) exports, \(D\) domestic demand/sales and \(Q^{refinery}\) refinery output.

Price analysis is conducted primarily **before taxes**, with after-tax prices reported separately. Spain is used as a comparison series, not automatically as a causal counterfactual.

## Identification guardrails

The report must distinguish:

- a documented industrial event;
- a structural break in an outcome series;
- an association after an event; and
- a causal effect.

A break near 2021/2022 does not, by itself, prove the Matosinhos closure caused the change. COVID recovery, the invasion of Ukraine, Russian VGO disruption, Sines maintenance, demand changes and common European price shocks are competing explanations that must be modelled or discussed.

## Environment

Python 3.11+, Poetry, JupyterLab.

```bash
poetry install
poetry run pytest
poetry run python scripts/run_notebooks.py
```

Run notebooks individually while developing. The sequential runner is primarily for reproducibility checks.
