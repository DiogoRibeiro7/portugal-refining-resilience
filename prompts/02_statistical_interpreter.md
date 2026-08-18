# Statistical Interpreter

Interpret the completed notebook-first analysis before report prose is drafted.

## Evidence Boundary

Use only:

- `artifacts/report_inputs/report_manifest.json`
- machine-readable files listed in that manifest
- documented event metadata in `refinery_events.csv`
- `reports/data_audit.md`

Do not recover numbers from chat, notebook prose, notebook display output, external memory or web searches.

## Task

Write `reports/interpretation_memo.md` answering:

1. What changed in exports, imports, refinery output and demand around 2013?
2. What changed around the 2021 Matosinhos transition in monthly data?
3. Is 2022 exceptional under the explicit benchmark windows and monthly event phases?
4. Did gross import dependence and net-import-to-demand ratios change materially?
5. Did refinery-output-to-demand ratios change?
6. Do break diagnostics align with predeclared event dates after transition-year exclusions?
7. What do price co-movement models show about the `ES_x_post` interaction?
8. Did Portugal-Spain pre-tax spreads change, and do diagnostics support stronger interpretation?
9. Which results survive sensitivity checks?
10. Which tempting claims are not supported?

Use only these evidence levels: `documented event`, `descriptive change`, `statistical association / structural-break evidence`, `causal evidence`.
