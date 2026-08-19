# Data provenance for the report

Where every table and figure in [`report_final.tex`](report_final.tex) comes from.

The paper itself does not name internal files. This document is the mapping, so a reader who
wants to check a number can find the exact table it came from, and a reader who wants to rerun
the analysis can find the notebook that produced it.

All derived files live in `artifacts/report_inputs/`, the checksum-protected evidence bundle.
Its `report_manifest.json` records a SHA-256 for every file and accounts for every file in the
directory: anything present but unmanifested is removed when the bundle is rebuilt.

## Windows

Each arm runs over the full study window intersected with what its own source provides.

| Arm | Window | Limited by |
|---|---|---|
| Annual physical balance | 1990–2024 | Eurostat, earliest published year |
| Monthly event models | 2002–2024 | JODI, earliest published month |
| Weekly price models | 2005–2024 | EC Weekly Oil Bulletin |

## Primary sources

| Source | What it provides | Coverage used | Acquisition notebook |
|---|---|---|---|
| JODI Oil World Database | Monthly imports, exports, refinery output, demand | 2005–2024, complete | `03_acquire_jodi_oil.ipynb` |
| Eurostat `nrg_cb_oil` | Annual balance, PT and ES; **source for the annual panel** | 1990–2024, complete | `04_acquire_eurostat_oil_balance.ipynb` |
| DGEG trade workbooks | National import/export statistics | 2019–2024 only | `02_acquire_dgeg_trade_and_sales.ipynb` |
| DGEG long sales workbook | Domestic market sales | 1970–2024 | `02_acquire_dgeg_trade_and_sales.ipynb` |
| EC Weekly Oil Bulletin | Weekly pre- and post-tax consumer prices | 2005-01-03 to 2024-12-30 | `05_acquire_weekly_oil_prices.ipynb` |
| Galp disclosures | Dated refinery events (metadata only) | 2013, 2020, 2021, 2022 | `06_refinery_events_and_capacity.ipynb` |

Raw downloads are excluded from version control. Each carries a metadata sidecar recording
retrieval time, URL, SHA-256 and vintage status.

## Tables

| Table | Caption | Derived file | Produced by |
|---|---|---|---|
| 1 | Source coverage | `jodi_trade_annual_completeness.csv`, `jodi_demand_annual_completeness.csv`, `jodi_refinery_output_annual_completeness.csv`, `eurostat_physical_balance_panel.csv` | `07`–`09`, `04` |
| 2 | Diesel annual balance | `fuel_annual_analytical_panel.csv` | `10_build_analytical_panel.ipynb` |
| 3 | Gasoline annual balance | `fuel_annual_analytical_panel.csv` | `10_build_analytical_panel.ipynb` |
| 4 | Balance at the event years | `headline_event_years.csv`, `refining_regime_annual.csv` | `18`, `06` |
| 5 | Chow tests | `structural_break_tests.csv` | `13_structural_breaks.ipynb` |
| 6 | Interrupted-trend models | `annual_interrupted_trend_models.csv` | `13_structural_breaks.ipynb` |
| 7 | Diesel monthly phase means (2002-2024) | `monthly_event_phase_summary.csv` | `14_monthly_event_analysis.ipynb` |
| 8 | Segmented monthly event model (n=276) | `monthly_event_models.csv` | `14_monthly_event_analysis.ipynb` |
| 9 | Short-run pass-through | `price_short_run_models.csv` | `15_price_comovement.ipynb` |
| 10 | Gasoline error-correction model | `price_ecm_models.csv` | `15_price_comovement.ipynb` |
| 11 | Diesel balance, Portugal against Spain | `pt_es_physical_balance_comparison.csv` | `16_spain_comparison.ipynb` |
| 12 | 2022 diesel exports by source | `stress_2022_source_sensitivity.csv` | `14_2022_stress_test.ipynb` |
| 13 | 2022 interrupted-trend level changes by source | `annual_source_sensitivity.csv` | `17_robustness_and_sensitivity.ipynb` |
| 14 | Pre/post difference by window | `event_window_sensitivity.csv` | `17_robustness_and_sensitivity.ipynb` |

## Figures

| Figure | Caption | Image | Produced by |
|---|---|---|---|
| 1 | Diesel physical balance | `diesel_physical_balance.png` | `11_descriptive_trade_and_supply.ipynb` |
| 2 | Gasoline physical balance | `gasoline_physical_balance.png` | `11_descriptive_trade_and_supply.ipynb` |
| 3 | Diesel dependence ratios | `diesel_dependence_ratios.png` | `12_import_dependence_and_refinery_output_ratio.ipynb` |
| 4 | Gasoline dependence ratios | `gasoline_dependence_ratios.png` | `12_import_dependence_and_refinery_output_ratio.ipynb` |
| 5 | Monthly diesel net imports to demand | `monthly_event_diesel_net_import_to_demand_ratio.png` | `14_monthly_event_analysis.ipynb` |
| 6 | Monthly diesel imports and exports | `monthly_event_diesel_imports_kt.png`, `monthly_event_diesel_exports_kt.png` | `14_monthly_event_analysis.ipynb` |
| 7 | Monthly gasoline imports and exports | `monthly_event_gasoline_imports_kt.png`, `monthly_event_gasoline_exports_kt.png` | `14_monthly_event_analysis.ipynb` |
| 8 | Monthly gasoline net imports to demand | `monthly_event_gasoline_net_import_to_demand_ratio.png` | `14_monthly_event_analysis.ipynb` |
| 9 | PT–ES pre-tax price spreads | `pt_es_diesel_pretax_price_spread.png`, `pt_es_gasoline_pretax_price_spread.png` | `16_spain_comparison.ipynb` |

## Numbers quoted in the text but not tabulated

| Statement | Derived file |
|---|---|
| Window means and peaks for both products | `descriptive_metrics.csv` |
| Monthly panel span and modelled months | `fuel_monthly_analytical_panel.csv` |
| 2022 z-scores, robust z-scores and baseline percentiles | `stress_2022_metrics.csv` |
| 2022 diesel exports computed on each trade source | `stress_2022_source_sensitivity.csv` |
| ADF results for the four price levels | `price_stationarity_diagnostics.csv` |
| Cointegration verdicts and selected model family | `price_model_choice.csv` |
| Levels regression, flagged not valid for inference | `price_comovement_models.csv` |
| Mean PT–ES spread before and after the transition | `pt_es_price_spread_summary.csv` |
| ADF results for the two spreads | `pt_es_spread_stationarity.csv` |
| Headline pre/post dependence change | `dependence_pre_post_summary.csv` |
| JODI/DGEG agreement share and named divergences | `jodi_dgeg_trade_reconciliation.csv`, `config/analysis.yml` |
| Frozen source identifiers and retrieval points | `source_manifest_snapshot.csv` |
| Pre-specified hypotheses | `research_design.csv` |
| Product comparability judgements | `data/reference/product_definition_crosswalk.csv` |

## How this mapping is enforced

The table-to-file mapping above is not documentation alone. `config/report_tables.yml`
carries the machine-readable version, and notebook 20 blocks the report unless:

- every number printed in a mapped table is reproducible from that table's declared file,
  at the precision the report prints;
- every sample size stated as `n=...` matches a fitted model;
- an interval stated in words matches the configured event dates;
- every trade cell the reconciliation flags has a sensitivity computed for it.

Results that change significance when the trade source is swapped are reported rather than
blocked, so they cannot pass unnoticed. Results are in `data/metrics/report_claim_checks.csv`.

`tab:coverage` is declared narrative: its cells are sentences, so cell-level verification
would compare prose against a numeric frame.

## Reproducing the analysis

```bash
poetry install
make notebooks     # executes notebooks 00-20 against the live sources
make report-pdf    # builds reports/report_final.pdf
```

`make notebooks` re-downloads from the five public sources, rebuilds `data/`, `figures/`,
`tables/` and the evidence bundle, and runs the readiness gate. The gate blocks the report
unless all eight checks pass; they are recorded in `data/metrics/report_readiness.csv`.

Notebook execution state is discarded by default, so a pipeline run does not put twenty-two
notebooks into the diff. Pass `--save-outputs` to `scripts/run_notebooks.py` if you want it kept.
