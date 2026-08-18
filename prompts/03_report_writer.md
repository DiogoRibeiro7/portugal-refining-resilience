# Report Writer

Write a rigorous data-analysis report in English titled:

> From Refining Capacity to Import Dependence: Portugal's Diesel and Gasoline Market, 2005-2024

Save it as LaTeX to `reports/drafts/report_v1.tex`.

## Required Evidence

Read first:

- `reports/data_audit.md`
- `reports/interpretation_memo.md`
- every machine-readable file listed by `artifacts/report_inputs/report_manifest.json`

Do not use numbers from memory, prior chat, notebook display output, notebook prose or external sources. If a number is not saved in the empirical bundle, omit it or flag it as unavailable.

## Required Concepts

Use:

```text
NetImports[j,t] = M[j,t] - X[j,t]
NetImportToDemandRatio[j,t] = (M[j,t] - X[j,t]) / D[j,t]
RefineryOutputToDemandRatio[j,t] = Q_refinery[j,t] / D[j,t]
```

Do not call `RefineryOutputToDemandRatio` self-sufficiency. Portuguese refinery output may be exported while domestic demand is met partly by imports.

Treat annual 2021 as a transition year. Use `fuel_monthly_analytical_panel.csv`,
`monthly_event_phase_summary.csv`, and `monthly_event_models.csv` to distinguish May 2021
closure timing from the March 2022 energy shock.

Price analysis is Portugal-Spain retail price co-movement unless an actual international wholesale benchmark is included.
