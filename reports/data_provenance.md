# Data provenance for the report

Where every table and figure in [`report_final.tex`](report_final.tex) comes from.

The paper itself does not name internal files. This document is the mapping, so a reader who
wants to check a number can find the exact table it came from, and a reader who wants to rerun
the analysis can find the notebook that produced it.

Except where a row below gives another path, every derived file named here lives in
`artifacts/report_inputs/`, the checksum-protected evidence bundle.
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
| JODI Oil World Database | Monthly imports, exports, refinery output, demand | 2002–2024, complete | `03_acquire_jodi_oil.ipynb` |
| Eurostat `nrg_cb_oil` | Annual balance, PT and ES; **source for the annual panel** | 1990–2024, complete | `04_acquire_eurostat_oil_balance.ipynb` |
| DGEG trade workbooks | National import/export statistics | 2019–2024 only | `02_acquire_dgeg_trade_and_sales.ipynb` |
| DGEG long sales workbook | Domestic market sales | 1970–2024 | `02_acquire_dgeg_trade_and_sales.ipynb` |
| EC Weekly Oil Bulletin | Weekly pre- and post-tax consumer prices | 2005-01-03 to 2024-12-30; 995 of 1,044 weeks for PT, 994 for ES | `05_acquire_weekly_oil_prices.ipynb` |
| Galp disclosures | Dated refinery events (metadata only) | 2013, 2020, 2021, 2022 | `06_refinery_events_and_capacity.ipynb` |

The bulletin does not publish every week. The gaps are dropped rather than interpolated, and
`weekly_price_coverage.csv` records how many weeks are missing, how long the longest gap runs
and how many are fortnightly rather than weekly.

Raw downloads are excluded from version control. Each carries a metadata sidecar recording
retrieval time, URL, SHA-256 and vintage status.

## Tables

Generated from `reports/report_final.aux` and `config/report_tables.yml` by
`scripts/refresh_provenance.py`, so the numbering cannot drift from the built document.

| Table | Caption | Derived file | Produced by |
|---|---|---|---|
| 1 | Source coverage | narrative; see below | `07`-`09`, `04` |
| 2 | Diesel annual balance | `fuel_annual_analytical_panel.csv` | `10_build_analytical_panel.ipynb` |
| 3 | Gasoline annual balance | `fuel_annual_analytical_panel.csv` | `10_build_analytical_panel.ipynb` |
| 4 | Balance at the event years | `headline_event_years.csv` | `18`, `06` |
| 5 | Chow tests at candidate break years | `structural_break_tests.csv` | `13_structural_breaks.ipynb` |
| 6 | Interrupted-trend models, both 2022 specifications | `annual_interrupted_trend_models.csv` | `13_structural_breaks.ipynb` |
| 7 | Diesel monthly phase means | `monthly_event_phase_summary.csv` | `14_monthly_event_analysis.ipynb` |
| 8 | Segmented monthly event model, both specifications | `monthly_event_models.csv` | `14_monthly_event_analysis.ipynb` |
| 9 | 2022 diesel exports by trade source | `stress_2022_source_sensitivity.csv` | `14_2022_stress_test.ipynb` |
| 10 | Contemporaneous elasticity, difference-only model | `price_short_run_models.csv` | `15_price_comovement.ipynb` |
| 11 | Error-correction models | `price_ecm_models.csv` | `15_price_comovement.ipynb` |
| 12 | Diesel balance ratios, Portugal against Spain | `pt_es_physical_balance_comparison.csv` | `16_spain_comparison.ipynb` |
| 13 | Pre/post difference by window | `event_window_sensitivity.csv` | `17_robustness_and_sensitivity.ipynb` |
| 14 | Claim-evidence matrix | narrative; see below | written prose; every row checked against the table it cites |
| 15 | Monthly arm against annual arm, four balance terms | `monthly_annual_agreement_summary.csv` | `17_robustness_and_sensitivity.ipynb` |
| 16 | 2022 interrupted-trend level changes by source | `annual_source_sensitivity.csv` | `17_robustness_and_sensitivity.ipynb` |

## Figures

| Figure | Caption | Image | Produced by |
|---|---|---|---|
| 1 | Diesel physical balance | `diesel_physical_balance.png` | `11` |
| 2 | Gasoline physical balance | `gasoline_physical_balance.png` | `11` |
| 3 | Diesel dependence ratios | `diesel_dependence_ratios.png` | `12` |
| 4 | Gasoline dependence ratios | `gasoline_dependence_ratios.png` | `12` |
| 5 | Monthly diesel net imports to demand | `monthly_event_diesel_net_import_to_demand_ratio.png` | `14` |
| 6 | Monthly diesel imports and exports | `monthly_event_diesel_imports_kt.png`, `monthly_event_diesel_exports_kt.png` | `14` |
| 7 | Monthly gasoline imports and exports | `monthly_event_gasoline_imports_kt.png`, `monthly_event_gasoline_exports_kt.png` | `14` |
| 8 | Monthly gasoline net imports to demand | `monthly_event_gasoline_net_import_to_demand_ratio.png` | `14` |
| 9 | PT-ES pre-tax price spreads | `pt_es_diesel_pretax_price_spread.png`, `pt_es_gasoline_pretax_price_spread.png` | `16` |
| 10 | PT and ES diesel coverage, full window | `pt_es_diesel_output_ratio_full_window.png` | `16` |

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
| Diesel and gasoline coverage-ratio range, and the years either crosses one | `fuel_annual_analytical_panel.csv` |
| ADF verdicts under every lag rule and deterministic term | `price_adf_lag_sensitivity.csv` |
| The same diagnostics on EUR levels, showing where the scales disagree | `price_model_choice_scale_comparison.csv` |
| KPSS, run with stationarity as the null | `price_kpss_diagnostics.csv` |
| Half-lives implied by each adjustment speed | `price_ecm_half_lives.csv` |
| Long-run slope tested against one, by dynamic least squares | `price_cointegrating_slope_tests.csv` |
| Contemporaneous elasticity tested against one rather than zero | `price_elasticity_unit_tests.csv` |
| Adjustment speed re-estimated on subsets of the post period | `price_post_period_stability.csv` |
| Cointegration allowing the long-run relation to shift at an unknown date | `price_regime_shift_cointegration.csv` |
| Johansen rank tests, the system cross-check | `price_johansen_rank_tests.csv` |
| Second break tested at March 2022, with each regime's level | `price_second_break_tests.csv` |
| Spread unit-root tests within each regime as well as pooled | `pt_es_spread_stationarity_by_regime.csv` |
| Weeks the bulletin published, and the gaps | `weekly_price_coverage.csv` |
| The same specification on four neighbouring countries | `price_cross_country_placebo.csv` |
| False break dates, estimated on pre-closure data only | `price_false_break_placebo.csv` |
| The cross-country comparison at both candidate dates | `price_placebo_by_break_date.csv` |
| Adjustment speed in each of three phases, per country pair | `price_phase_adjustment_speeds.csv` |
| Break dates searched rather than assumed, with a simulated null | `exploratory_break_sup_wald.csv` |
| Breaks located jointly, number chosen by BIC | `joint_break_search.csv` |
| Fit and residual diagnostics for the annual models | `annual_model_residual_diagnostics.csv` |
| Monthly arm against annual arm, cell by cell | `monthly_annual_balance_reconciliation.csv` |
| JODI against Eurostat, cell by cell and summarised | `jodi_eurostat_trade_reconciliation.csv`, `jodi_eurostat_reconciliation_summary.csv` |
| Dated refinery events used as metadata | `refinery_events.csv` |
| Interpreter, library versions and platform | `software_environment.csv` |
| Months reported per year, per JODI flow, and the years that fall short of twelve | `jodi_trade_annual_completeness.csv`, `jodi_refinery_output_annual_completeness.csv`, `jodi_demand_annual_completeness.csv` |
| The Eurostat annual panel as extracted, before the analytical panel is built | `eurostat_physical_balance_panel.csv` |

## How this mapping is enforced

The table-to-file mapping above is not documentation alone. `config/report_tables.yml`
carries the machine-readable version, and notebook 20 blocks the report unless:

- every number printed in a mapped table is reproducible from that table's declared file,
  at the precision the report prints;
- every quantity stated in the prose, including the claim-evidence matrix, is reproducible from
  the bundle. Figures the text derives rather than reads, such as a half-life computed from an
  adjustment coefficient, are declared in `config/report_tables.yml` under `prose_allow`;
- every sample size stated as `n=...` matches a fitted model;
- an interval stated in words matches the configured event dates;
- every trade cell the reconciliation flags has a sensitivity computed for it;
- no claim quotes a coefficient from a model family the diagnostics did not select;
- no estimate from a superseded specification is quoted without naming the specification.
  Both fits of the monthly model are persisted, so the earlier estimates stay in the bundle and
  every numeric check keeps accepting them; requiring attribution is what catches it;
- no bundle artifact covers years the study window excludes, unless declared;
- every quantity carrying a unit is written in maths mode, where the numeric checks can read it.

Twelve checks run in total, against the report and against `article.tex` separately. The
article passed the eleven that existed for several revisions while quoting the uncorrected
monthly fit, which is why the twelfth exists.

### What the gate does not check
The table check is containment: each value printed in a mapped table must appear somewhere in
that table's declared file, within half a unit of the last digit the report prints. It is not
position-aware, and the difference is worth stating. Falsifying a cell to a value the file does
not hold anywhere fails the check; falsifying it to a value the file holds in another column
does not. Both were confirmed by doing them: the 2023 diesel imports cell was changed to 7,777
and the check failed, then to 3,487, the net-imports figure from the next column, and it passed.
A value transposed within its own source is therefore not caught.

Year-like values used to be skipped outright, on the reasoning that a year indexes a row rather
than asserting anything. That holds for a row label and fails for the Break column of the Chow
table, where the year is the finding: the table could name any break year and pass, which was
confirmed by changing a diesel export break from 2013 to 2007 and watching the check stay green.
A year is now skipped only when no declared source carries years as data, which distinguishes
`break_year` in the break tests from the 2013 and 2022 that appear inside model term labels.


The two documents are checked separately, each against the bundle, and nothing compares them to
each other. Both fits of the monthly model are in the bundle, so an estimate from the superseded
fit is a valid bundle number: in principle the report and the article could each pass while
quoting different specifications. That is close to what happened before the twelfth check.

Shared tables are not exposed to this. The article uses nine table labels, all of them among the
report's sixteen; both documents resolve a label through the same mapping and are checked against
the same file, so a table cannot disagree between them. The exposure is prose.

Containment was tried too, the guard that works for `report_final.md`, and it does not transfer.
Of 898 numeric tokens in the article, 14 are absent from the report: thirteen are standard
errors, which the article prints where the report switched to confidence intervals, and the last
is a refinery-output score the report states no figure for. All are reproducible from the bundle
and all pass the article's own checks, so the guard would be fourteen false alarms. Containment
earns its place on a document the gate does not cover, and adds nothing to one it does.

A numeric cross-check on prose was tried and is not part of the gate, because it cannot
discriminate. At two decimals the estimates from the two fits collide with each other and with
unrelated numbers in the text; at three or more, neither document quotes most of them at all.
This is the same reason `check_prose_percentages` was removed and the reason the twelfth check
requires an attribution rather than a matching value. Agreement between the two documents in
prose is established by reading them, not by the gate.

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

`make report-inputs` rebuilds the evidence bundle and reruns the gate on their own,
without re-downloading; `--only` takes any notebook numbers.

`make notebooks` re-downloads from the five public sources, rebuilds `data/`, `figures/`,
`tables/` and the evidence bundle, and runs the readiness gate. The gate blocks the report
unless all eight checks pass; they are recorded in `data/metrics/report_readiness.csv`.

### What a rerun reproduced

The notebooks were executed end to end against the live sources on 23 August 2026, after v0.5.0
was tagged. Every derived file matched the committed version, apart from line endings and the
`created_at_utc` field in the metadata sidecars: no CSV or Parquet content changed.

That is one observation rather than a guarantee. Eurostat and DGEG revise, JODI backfills, and a
rerun after a revision should be expected to differ. The property worth rechecking is not that
the numbers come back identical but that the readiness and claim gates still pass, and that any
number the report prints still matches the file behind it.

Notebook execution state is discarded by default, so a pipeline run does not put twenty-two
notebooks into the diff. Pass `--save-outputs` to `scripts/run_notebooks.py` if you want it kept.
