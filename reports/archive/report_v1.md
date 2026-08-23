# From Refining Capacity to Import Dependence: Portugal's Diesel and Gasoline Market, 2005-2024

> **Superseded.** This is a staged artifact from the report-writing chain, written when the
> evidence bundle was empty. It does not describe current findings. The canonical report is
> [`report_final.tex`](../report_final.tex).

## 1. Executive Summary

This draft evaluates what can be written from the repository's stored reporting
evidence. The current evidence supports a dated institutional timeline: the
Sines hydrocracker entered commercial production in 2013, Galp announced a
concentration of refining activity at Sines in December 2020, Matosinhos
refining activities ceased during 2021, and 2022 included a documented
feedstock shock relevant to diesel manufacturing.

The current evidence does not support numerical conclusions about exports,
imports, demand, refinery output, import dependence, refinery-output-to-demand ratios,
structural breaks, price co-movement, or Portugal-Spain spreads. The required
report input manifest is absent, and `artifacts/report_inputs/` contains no
machine-readable empirical bundle. This report therefore treats quantitative
results as unavailable rather than inferring them from notebook state or memory.

The main conclusion is procedural and evidentiary: a publication-ready report
requires the report input bundle to be generated and audited before claims about
physical dependence, resilience, or prices can be made.

## 2. Research Question and Hypotheses

The motivating question is whether the loss or concentration of refining
capacity changed Portugal's dependence on imported finished petroleum products
and reduced supply resilience, and whether price co-movement changed after the
Matosinhos transition.

The intended hypotheses are:

- increased diesel-producing capability at Sines in 2013 may have changed
  diesel trade and refinery-output balances;
- the 2021 Matosinhos transition may have changed import dependence and domestic
  output coverage;
- 2022 may represent a supply-system stress episode;
- price co-movement may have changed after 2021, but domestic refining does not
  imply insulation from international crude or input prices.

These hypotheses cannot be evaluated quantitatively from the current reporting
bundle because the bundle is missing.

## 3. Institutional and Refining Timeline

The stored event metadata supports four documented events:

- 2013: the Sines hydrocracker entered commercial production.
- 2020: Galp announced concentration of core refining at Sines and
  discontinuation at Matosinhos from 2021.
- 2021: Matosinhos refining activities ceased during the year.
- 2022: Galp announced suspension of Russian oil-product purchases, with VGO
  noted as a relevant diesel-manufacturing feedstock at Sines.

Annual 2021 should be treated as a transition year. It should not be described
as a full post-closure year unless a saved model explicitly uses monthly timing.

## 4. Data and Product Definitions

The intended analysis covers diesel/gasoil and gasoline for Portugal, with Spain
as a comparison country. Configuration files define the primary price analysis
as prices without taxes, with after-tax prices as secondary.

The available audit cannot verify the report-ready product definitions against
the reporting bundle because `artifacts/report_inputs/report_manifest.json` is
missing. Available seed files are marked `seed_provisional`; they are not a
complete empirical basis for the report.

## 5. Methods

The intended physical-balance analysis uses transparent accounting metrics:

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

The price analysis should distinguish exposure to international crude or input
prices from dependence on imported finished petroleum products. Domestic
refining capacity can change physical supply exposure without eliminating world
price exposure.

No model estimates are reported here because no model-output files are present
in the reporting bundle.

## 6. Long-Run Trade and Refinery-Output Evidence

Unavailable. The current report bundle does not provide report-ready annual
imports, exports, demand, or refinery-output tables. The report cannot state
long-run changes in trade or output without those stored inputs.

## 7. The 2013 Sines Hydrocracker Break

The 2013 Sines hydrocracker is a documented event. It is reasonable to treat it
as an event date to test for changes in diesel-producing capability.

The current evidence does not show whether diesel exports, imports, refinery
output, domestic demand, or import dependence changed around 2013. Those are
empirical claims requiring stored tables or model outputs that are not present.

## 8. The 2021 Matosinhos Transition

The cessation of refining at Matosinhos during 2021 is a documented event.
Annual 2021 should be handled as a transition year.

The current evidence does not show whether the transition changed imports, net
imports, domestic output coverage, or supply resilience. Those results require
the missing report input bundle.

## 9. 2022 as a Supply-System Stress Test

The event metadata identifies 2022 as a competing mechanism and stress episode
because of the Russian oil-product/VGO disruption. That supports treating 2022
as a period requiring special interpretation.

The current evidence does not show which physical-balance terms account for any
2022 movement. No report-ready decomposition is available.

## 10. Import Dependence and Domestic Supply Coverage

Unavailable. Gross import dependence, net import dependence, and domestic
refinery-output coverage cannot be reported without stored values for imports,
exports, demand, and refinery output.

## 11. Price Co-Movement and Portugal-Spain Comparison

The intended primary price outcome is pre-tax fuel prices. This design choice is
important because tax changes can contaminate after-tax retail price comparisons.

The current evidence does not include price-model outputs, price stationarity
diagnostics, or Portugal-Spain spread diagnostics. Therefore, the
physical-dependence analysis cannot establish a price effect. It also cannot use
Spain as a causal control. Spain can only be described as a planned comparison
series until saved diagnostics show otherwise.

## 12. Robustness and Source Reconciliation

The audit identifies DGEG as a required cross-check for Portuguese trade data,
but no stored reconciliation output is present in the reporting bundle.
Eurostat physical-balance outputs are also absent, so production, imports,
exports and domestic use cannot yet be reconciled in a full product-balance
framework.

No event-window sensitivity table, source-reconciliation table, or robustness
metric is available for this draft.

## 13. Limitations

The primary limitation is missing evidence, not statistical ambiguity. The
required reporting manifest is absent, and the report input directory contains
no empirical bundle. The repository includes seed/provisional data, but those
files are not the approved source of truth for report writing.

Because the data bundle is absent, this draft cannot assess:

- annual coverage or missing years;
- monthly event timing around May 2021 and March 2022;
- compatibility of trade, demand, and refinery-output concepts;
- source reconciliation against DGEG;
- Eurostat physical-balance ratios and residuals;
- structural-break sample sizes or estimates;
- event-window sensitivity;
- price co-movement estimates and stationarity diagnostics;
- Portugal-Spain pre-tax spreads.

## 14. Conclusions

The repository currently supports a carefully bounded institutional timeline and
methodological framework. It does not yet support substantive quantitative
claims about import dependence, resilience, or price effects.

Before publication, the pipeline should generate `artifacts/report_inputs/`,
including `report_manifest.json`, and the resulting bundle should pass the data
audit. Only then should the report state measured changes or model results.

## 15. Data and Reproducibility Appendix

The report was written against the available reporting artifacts:

- `reports/data_audit.md`
- `reports/interpretation_memo.md`
- `data/reference/refinery_events.csv`

The expected empirical source of truth,
`artifacts/report_inputs/report_manifest.json`, is absent. No numerical claim in
this draft is taken from notebook display output, prior conversation, or memory.
