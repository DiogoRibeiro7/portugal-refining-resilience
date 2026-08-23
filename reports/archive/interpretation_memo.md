# Interpretation Memo

> **Superseded.** This is a staged artifact from the report-writing chain, written when the
> evidence bundle was empty. It does not describe current findings. The canonical report is
> [`report_final.tex`](../report_final.tex).

## Evidence Boundary

This memo uses only the allowed evidence:

- `reports/data_audit.md`
- `data/reference/refinery_events.csv`

The required file `artifacts/report_inputs/report_manifest.json` is absent, and
`artifacts/report_inputs/` contains no machine-readable empirical bundle. The
audit therefore classifies the report-input layer as blocked. Numeric claims
about trade, demand, refinery output, import dependence, price models, break
diagnostics, and sensitivity checks are unavailable from the permitted evidence.

## Evidence-Level Summary

| Topic | Evidence level | Interpretation |
|---|---|---|
| Sines hydrocracker entered commercial production in 2013 | documented event | Event metadata records a capacity upgrade at Sines, with the analytical role of a pre-specified positive diesel-capability break. |
| Galp announced concentration of refining at Sines in December 2020 | documented event | Event metadata records the announcement date and warns not to use it as the physical closure date. |
| Matosinhos refining activities ceased during 2021 | documented event | Event metadata records May 2021 as the closure timing and states that annual 2021 should be treated as a transition year. |
| 2022 Russian oil-product/VGO disruption | documented event | Event metadata records a competing mechanism and stress shock relevant to diesel manufacturing at Sines. |
| Diesel/gasoline exports, imports, demand, output, import dependence, price co-movement, Portugal-Spain spread | unavailable | The empirical bundle needed for numerical interpretation is absent. |

## Answers to the Analytical Questions

### 1. What changed around 2013?

The permitted evidence supports only a **documented event**: the Sines
hydrocracker entered commercial production in 2013. The event metadata describes
this as relevant to diesel-producing capability.

No **descriptive change** in diesel exports, imports, refinery output, or
domestic demand can be stated from the permitted evidence because the report
input bundle is missing.

### 2. What changed around the 2021 Matosinhos transition?

The permitted evidence supports a **documented event**: Matosinhos refining
activities ceased during 2021, and annual 2021 should be treated as a transition
year rather than a full post-closure year.

No **descriptive change** in physical balances can be stated from the permitted
evidence.

### 3. Is 2022 exceptional, and which physical-balance terms account for it?

The permitted evidence supports a **documented event**: 2022 includes a
documented feedstock shock related to Russian oil-product purchases and VGO.

Whether 2022 is empirically exceptional, and whether imports, exports, demand,
or refinery output account for the change, is unavailable from the permitted
evidence.

### 4. Did gross and net import dependence change materially after the transition?

Unavailable. Gross and net import-dependence metrics are not present in the
permitted evidence.

### 5. Did domestic refinery-output coverage change?

Unavailable. Domestic refinery-output coverage is not present in the permitted
evidence.

### 6. Do formal break diagnostics align with documented event dates?

Unavailable. The audit notes that break-test settings exist in configuration,
but no stored break-model outputs are present in the report bundle.

### 7. What do the price models show about pre-tax price co-movement?

Unavailable. The audit records that configuration identifies pre-tax prices as
the primary measure, but no stored price-model output is available.

### 8. Did the Portugal-Spain pre-tax spread change?

Unavailable. Spain is configured as a comparison country, but no stored
Portugal-Spain spread or pre-trend diagnostics are present in the permitted
evidence.

### 9. Which results survive event-window sensitivity checks?

Unavailable. No event-window sensitivity outputs are present in the permitted
evidence.

### 10. Which tempting claims are not supported?

The following claims are **not supported** by the permitted evidence:

- that the Sines hydrocracker caused a measured change in diesel exports,
  imports, demand, or refinery output;
- that the Matosinhos closure caused a measured change in import dependence;
- that 2022 physical-balance changes are attributable to Matosinhos rather than
  broader European energy shocks or feedstock disruption;
- that Portugal's retail fuel prices rose because of the Matosinhos closure;
- that Spain can be used as a causal control rather than a comparison series;
- that any structural break has sufficient statistical support;
- that any report-ready numerical claim can be made from the missing empirical
  bundle.

## Bottom Line

The permitted evidence supports a dated institutional timeline and clear
interpretive guardrails. It does not support numerical findings or causal
claims. A substantive interpretation requires a complete
`artifacts/report_inputs/report_manifest.json` and the machine-readable files
listed by that manifest.
