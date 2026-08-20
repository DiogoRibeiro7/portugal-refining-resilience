# Adversarial Peer Review

## Review Scope

Reviewed files:

- `reports/drafts/report_v1.md`
- `reports/data_audit.md`
- `reports/interpretation_memo.md`
- `data/reference/refinery_events.csv`
- `artifacts/report_inputs/`

The required `artifacts/report_inputs/report_manifest.json` is absent, and
`artifacts/report_inputs/` contains no empirical CSV or JSON files. The review
therefore focuses on whether the draft overstates evidence despite that absence.

## Overall Assessment

The draft is appropriately conservative. It does not report unsupported
estimates, does not use the seed data as publication-ready evidence, and does
not infer causal price effects from the Matosinhos transition.

However, the draft currently reads as an evidence-limited interim report rather
than a completed empirical data-analysis report. That limitation is correctly
disclosed, but it should be made even more explicit in the final version to
avoid readers mistaking the document for a completed 2005-2024 analysis.

## Findings

| # | Review item | Classification | Finding | Exact revision needed |
|---|---|---|---|---|
| 1 | Source-definition mismatch | OK | The draft does not combine source series or make claims from incompatible definitions. | None. |
| 2 | Tonnes, litres, and energy-unit confusion | OK | The draft states the intended physical-balance formulas but does not report numeric quantities across mixed units. | None. |
| 3 | Motor gasoline versus broader gasoline-category mismatch | OK | The draft does not make a gasoline-category claim beyond noting intended product scope. | None. |
| 4 | Gross imports versus net imports confusion | OK | The draft defines net imports and net import dependence correctly and does not conflate them with gross imports. | None. |
| 5 | Domestic sales versus final consumption confusion | OK | The draft does not report domestic sales or final consumption values. | None. |
| 6 | 2021 treated as full post-closure year | OK | The draft explicitly treats 2021 as a transition year. | None. |
| 7 | Small-sample structural-break overinterpretation | OK | No structural-break estimate is interpreted. | None. |
| 8 | 2022 Ukraine/VGO/common-European-shock confounding | OK | The draft identifies 2022 as a competing stress mechanism and does not attribute it to Matosinhos. | None. |
| 9 | Invalid causal use of Spain | OK | The draft states that Spain cannot be used as a causal control without stored diagnostics. | None. |
| 10 | Taxes contaminating price co-movement results | OK | The draft distinguishes pre-tax analysis from after-tax retail prices and reports no price estimate. | None. |
| 11 | Nominal capacity treated as actual output | OK | The draft does not treat capacity metadata as refinery output. | None. |
| 12 | Galp corporate claims treated as independent outcome evidence | OK | Galp disclosures are used only as event metadata. | None. |
| 13 | Missing source reconciliation | MAJOR | The draft correctly says DGEG reconciliation is missing, but this prevents a substantive trade-dependence report. | In the final version, state in the executive summary and conclusion that source reconciliation is absent and that no trade-dependence finding is publication-ready. |
| 14 | Claims stronger than stored metrics | MAJOR | The title and section structure imply a completed 2005-2024 empirical report, while stored metrics needed for those claims are absent. | In the final version, label the document as evidence-limited, remove or weaken any phrasing that implies measured 2005-2024 findings, and add a claim-evidence matrix showing every substantive claim has only documented-event or unavailable descriptive support. |

## Required Revisions

1. Strengthen the executive-summary caveat: this is not yet a completed
   empirical assessment of import dependence or price co-movement.
2. State that missing DGEG reconciliation blocks publication-ready trade claims.
3. Keep all post-2013, post-2021, 2022, and price statements at documented-event
   or unavailable-evidence level unless a stored report bundle is added.
4. Add a claim-evidence matrix that names the exact evidence file and remaining
   caveat for each claim.

## Reviewer Conclusion

The draft is cautious and methodologically sound given the missing evidence.
The final version should preserve that discipline and make the evidence-limited
status impossible to miss.
