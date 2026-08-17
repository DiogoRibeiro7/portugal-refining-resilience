# Empirical Bundle Audit

Prompt executed: `prompts/01_data_audit.md`

## Scope

This audit reviewed the files requested by the prompt:

- `artifacts/report_inputs/report_manifest.json`
- machine-readable files under `artifacts/report_inputs/`
- `config/analysis.yml`
- `config/sources.yml`
- `data/metrics/report_readiness.csv`, if present

The required empirical bundle is not currently available. The directory
`artifacts/report_inputs/` contains only `.gitkeep`; `report_manifest.json` is
absent. The optional readiness file `data/metrics/report_readiness.csv` is also
absent.

Because the manifest is missing, this audit cannot verify stored report-input
metrics. It does not calculate replacement metrics from raw, notebook, or chat
state.

## Findings

| Check | Status | Evidence | Notes |
|---|---|---|---|
| Report input manifest exists | BLOCKER | `artifacts/report_inputs/report_manifest.json` | Required starting point is missing. No machine-readable report bundle can be enumerated. |
| Report input files exist | BLOCKER | `artifacts/report_inputs/` | Directory contains only `.gitkeep`; no CSV or JSON evidence files are available for report writing. |
| Readiness audit exists | WARNING | `data/metrics/report_readiness.csv` | File is absent. The prompt treats it as optional, but its absence prevents an explicit readiness check. |
| Units and product definitions for diesel/gasoil and gasoline | WARNING | `config/analysis.yml`; `config/sources.yml`; `data/processed/jodi_portugal_fuel_exports_2005_2024_seed.csv` columns `product`, `flow`, `value_kt`, `status` | The available seed file uses `value_kt`, so tonnes are implied. Product-definition details cannot be verified against the missing report bundle. |
| Annual coverage and missing years | BLOCKER | `artifacts/report_inputs/report_manifest.json` | No manifest or report-input table is available to verify annual coverage. The seed export file is outside the requested bundle. |
| 2021 transition-year treatment | WARNING | `config/analysis.yml` key `event_years.matosinhos_transition`; `data/reference/refinery_events.csv` columns `event_year`, `analytical_role` | Configuration identifies 2021 as the Matosinhos transition year and event metadata says annual 2021 should not be treated as a full post-closure year. The report bundle does not exist, so downstream treatment cannot be audited. |
| Compatibility of trade, demand and refinery-output concepts | BLOCKER | `artifacts/report_inputs/report_manifest.json` | Missing bundle prevents checking whether trade, demand, and refinery-output series use compatible units, product definitions, and timing. |
| DGEG cross-check of trade series | BLOCKER | `config/sources.yml` key `dgeg_trade`; missing `data/metrics/report_readiness.csv`; missing report bundle | DGEG is configured as the primary Portugal trade cross-check, but no stored reconciliation result is present in the requested inputs. |
| `seed_provisional` flags | BLOCKER | `data/processed/jodi_portugal_fuel_exports_2005_2024_seed.csv` column `status`; `data/metrics/seed_export_metrics.csv` column `status` | Available seed data and seed metrics are marked `seed_provisional`. Because the report bundle is absent, there is no evidence that provisional values have been replaced or cross-validated. |
| Primary price analysis uses pre-tax prices | BLOCKER | `config/analysis.yml` key `price_analysis.primary_measure` | Configuration says primary measure is `without_taxes`, but no stored price-model output is available in the report bundle to audit. |
| Spain use as comparison or causal control | WARNING | `config/analysis.yml` keys `comparison_country`, `reporting.causal_language_requires_control_design` | Configuration identifies Spain as the comparison country and requires a control design for causal language. No report inputs are present to verify implementation. |
| Structural-break observations are sufficient | BLOCKER | `config/analysis.yml` key `annual_break_tests.minimum_segment_years` | Minimum segment length is configured as 5 years, but no break-model outputs are available for sample-size verification. |
| Numerical quantities needed to support proposed claims | BLOCKER | `artifacts/report_inputs/report_manifest.json` | No manifest or report input files are present. Numerical report claims cannot be supported from the requested empirical bundle. |

## Overall Assessment

The empirical bundle is not ready for report writing. The absence of
`artifacts/report_inputs/report_manifest.json` is the primary blocker. The
available committed data are seed/provisional exports and seed metrics, not the
complete report-input bundle required by the downstream prompts.

Before a substantive report is written, the notebook pipeline should create a
complete `artifacts/report_inputs/` bundle and a `data/metrics/report_readiness.csv`
file documenting whether source reconciliation, price models, break diagnostics,
and claim-supporting numerical quantities are available.
