# From Refining Capacity to Import Dependence: Portugal's Diesel and Gasoline Market, 2005-2024

## Evidence-Limited Final Report

This final report resolves the peer-review findings by making the evidence
status explicit. It is not a completed empirical assessment of Portugal's
2005-2024 diesel and gasoline import dependence. It is a bounded report on what
the repository's current stored evidence can and cannot support.

The required empirical report bundle is absent:

- `artifacts/report_inputs/report_manifest.json` is missing;
- `artifacts/report_inputs/` contains no empirical CSV or JSON files;
- `data/metrics/report_readiness.csv` is missing;
- no DGEG trade reconciliation output is available;
- no monthly event-timing panel is available;
- no Eurostat physical-balance panel is available;
- no price stationarity diagnostics are available.

Consequently, this report does not state measured changes in imports, exports,
demand, refinery output, import dependence, refinery-output-to-demand ratios,
structural breaks, price co-movement, or Portugal-Spain spreads.

## 1. Executive Summary

The repository currently supports a documented institutional timeline:

- the Sines hydrocracker entered commercial production in 2013;
- Galp announced concentration of core refining at Sines in December 2020;
- Matosinhos refining activities ceased during 2021;
- 2022 included a documented feedstock shock related to Russian oil products and
  VGO.

The repository does not yet support publication-ready quantitative findings
about physical import dependence or price effects. The missing DGEG
reconciliation is especially important: without it, the trade series cannot be
treated as independently cross-checked for a substantive import-dependence
claim. The missing monthly event-timing panel prevents the report from
distinguishing the May 2021 closure period from the March 2022 energy shock.
The missing Eurostat balance panel also prevents a full product-balance
cross-check of production, imports, exports and domestic use.

## 2. Research Question and Hypotheses

The intended research question is whether Portugal's refining-capacity changes
altered dependence on imported finished petroleum products and affected supply
resilience or price co-movement.

The intended hypotheses remain testable but untested from the current reporting
evidence:

- the 2013 Sines hydrocracker may have changed diesel-producing capability and
  trade balances;
- the 2021 Matosinhos transition may have changed import dependence and domestic
  refinery-output coverage;
- 2022 may represent a distinct supply-system stress episode;
- any price-transmission change must be evaluated using pre-tax prices and must
  not be inferred mechanically from refinery closure.

## 3. Institutional and Refining Timeline

The event metadata supports the following documented events.

| Year | Event | Evidence level | Interpretation |
|---:|---|---|---|
| 2013 | Sines hydrocracker entered commercial production | documented event | Pre-specified event relevant to diesel-producing capability. |
| 2020 | Galp announced concentration of refining at Sines | documented event | Announcement date; not a physical closure date. |
| 2021 | Matosinhos refining activities ceased during the year | documented event | Annual 2021 should be treated as a transition year. |
| 2022 | Russian oil-product/VGO disruption | documented event | Competing mechanism and stress shock relevant to diesel manufacturing. |

These events define the analytical calendar. They do not, by themselves,
demonstrate changes in imports, exports, output, or prices.

## 4. Data and Product Definitions

The intended products are diesel/gasoil and gasoline. The intended annual
physical metrics use thousand tonnes where stored. The intended price analysis
uses pre-tax prices as the primary measure.

These definitions cannot be verified against the final reporting bundle because
the bundle is absent. Available seed files are marked `seed_provisional` and are
not treated as publication-ready evidence here.

## 5. Methods

The intended physical-balance metrics are:

\[
\text{NetImports}_{j,t}=M_{j,t}-X_{j,t}
\]

\[
\text{NetImportToDemandRatio}_{j,t}=\frac{M_{j,t}-X_{j,t}}{D_{j,t}}
\]

\[
\text{RefineryOutputToDemandRatio}_{j,t}=\frac{Q^{refinery}_{j,t}}{D_{j,t}}.
\]

Here \(M\) is imports, \(X\) exports, \(D\) domestic demand or sales, and
\(Q^{refinery}\) refinery output for product \(j\) in year \(t\).

The current report does not estimate these metrics because the stored report
inputs are missing. It also does not estimate price co-movement, structural
breaks, or event-window sensitivity.

## 6. Physical-Balance Evidence

No report-ready annual table is available for imports, exports, demand, or
refinery output. Therefore:

- no long-run 2005-2024 trade trend is reported;
- no post-2013 diesel effect is reported;
- no post-2021 Matosinhos effect is reported;
- no 2022 decomposition is reported;
- no import-dependence or domestic-output-coverage metric is reported.

This is a deliberate evidentiary restriction, not an absence of analytical
interest.

## 7. Price Co-Movement and Portugal-Spain Comparison

No stored pre-tax price model output or price stationarity diagnostic is
available. The report therefore cannot establish a price effect.

Spain is an intended comparison country, but the current evidence does not
support using Spain as a causal control. Any future causal interpretation would
require stored diagnostics on pre-trends, common shocks, model specification,
and confounding from the 2022 European energy shock.

## 8. Robustness and Source Reconciliation

The data audit and peer review identify missing source reconciliation as a major
blocker. DGEG is configured as the primary Portugal trade cross-check, but no
stored DGEG reconciliation output is available in the report evidence.

Until source reconciliation is stored and audited, no trade-dependence finding is
publication-ready.

## 9. Limitations

The limitations are fundamental:

- missing report manifest;
- missing report input bundle;
- missing readiness file;
- seed/provisional data not replaced or cross-validated;
- missing DGEG reconciliation;
- missing monthly event-timing panel;
- missing Eurostat physical-balance output;
- missing structural-break outputs;
- missing price-model outputs and stationarity diagnostics;
- missing event-window sensitivity results.

The report therefore supports documented-event claims only. It does not support
descriptive, statistical-association, or causal claims about the main empirical
outcomes.

## 10. Conclusions

Portugal's refining timeline is documented in the repository, but the current
stored evidence is insufficient for a substantive 2005-2024 empirical report on
import dependence or price co-movement.

The next required step is to generate the report input bundle, including
`report_manifest.json`, DGEG reconciliation, monthly event-timing metrics,
Eurostat physical-balance metrics, structural-break outputs, price-model
outputs, price stationarity diagnostics and readiness checks. Once those files
exist, the report can be revised from an evidence-limited document into a
quantitative analysis.

## Claim-Evidence Matrix

| Claim | Evidence file | Metric/model | Evidence level | Remaining caveat |
|---|---|---|---|---|
| Sines hydrocracker entered commercial production in 2013. | `data/reference/refinery_events.csv` | event metadata | documented event | Corporate disclosure is event metadata, not independent outcome evidence. |
| Galp announced concentration of refining at Sines in December 2020. | `data/reference/refinery_events.csv` | event metadata | documented event | Announcement date is not the physical closure date. |
| Matosinhos refining activities ceased during 2021. | `data/reference/refinery_events.csv` | event metadata | documented event | Annual 2021 should be treated as a transition year. |
| 2022 included a relevant feedstock shock. | `data/reference/refinery_events.csv` | event metadata | documented event | Does not quantify any physical-balance effect. |
| The empirical report bundle is missing. | `reports/data_audit.md`; `artifacts/report_inputs/` | file-presence audit | descriptive | Describes repository state at the time of this report. |
| Available seed data are not publication-ready. | `reports/data_audit.md`; `data/processed/jodi_portugal_fuel_exports_2005_2024_seed.csv`; `data/metrics/seed_export_metrics.csv` | `status = seed_provisional` | descriptive | Seed files are outside the approved report-input bundle. |
| DGEG trade reconciliation is missing. | `reports/data_audit.md`; `reports/peer_review.md` | reconciliation availability audit | descriptive | Blocks publication-ready trade-dependence claims. |
| No measured import-dependence change can be reported. | `reports/data_audit.md`; `reports/interpretation_memo.md` | unavailable metric | descriptive | Requires stored imports, exports, demand, and reconciliation outputs. |
| No domestic-output-coverage change can be reported. | `reports/data_audit.md`; `reports/interpretation_memo.md` | unavailable metric | descriptive | Requires stored refinery-output and demand series. |
| No price effect can be established. | `reports/data_audit.md`; `reports/interpretation_memo.md` | unavailable price model | descriptive | Requires stored pre-tax price-model outputs and stationarity diagnostics. |
| Spain cannot currently be used as a causal control. | `reports/interpretation_memo.md`; `reports/peer_review.md` | unavailable comparison diagnostics | descriptive | Requires stored pre-trend and model diagnostics. |
| No causal claim is supported. | `reports/data_audit.md`; `reports/interpretation_memo.md`; `reports/peer_review.md` | evidence-level audit | descriptive | The design may support future causal language only after stored evidence exists. |
