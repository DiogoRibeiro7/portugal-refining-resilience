# From Refining Capacity to Import Dependence: Portugal's Diesel and Gasoline Market, 2005-2024

**The canonical report is [`report_final.tex`](report_final.tex).** Build it with `make report-pdf`.
This file is a summary; where the two differ, the LaTeX source is authoritative.

## Headline findings

All figures come from the checksum-protected bundle in `artifacts/report_inputs/`.

**The 2013 Sines hydrocracker produced an unambiguous structural change.** Diesel refinery
output, exports and the net-import-to-demand ratio all break at 2013 and survive
Benjamini-Hochberg adjustment across sixteen tests (adjusted *p* = 0.0026, 0.0027 and 0.0041).
Portugal moved from net diesel importer to net diesel exporter: refinery output covered
73-92% of diesel demand from 2005 to 2012, and 1.03-1.27 times demand from 2013 to 2020.

**After May 2021 the direction reverses.** By 2023 domestic diesel manufacturing covers only
66% of demand, the lowest in the twenty-year window, while diesel imports reach a series high
of 1,597 kt.

**A monthly design separates the closure from the 2022 shock.** Annual break tests at 2022
detect nothing, but they have only three post-event observations. A segmented monthly model
(n = 293, month fixed effects, HAC(3)) finds both episodes independently significant:

| Outcome | Matosinhos transition | Energy stress 2022 |
| --- | --- | --- |
| Refinery output | −105.2 kt/month (*p* = 0.004) | −151.8 kt/month (*p* < 0.001) |
| Net import / demand | +0.2005 (*p* = 0.005) | +0.3755 (*p* < 0.001) |

**2022 is a diesel-specific stress episode.** Against a 2013-2019 baseline, 2022 diesel exports
sit at the 0th percentile (*z* = −2.44) and imports at the 100th (*z* = +2.74). Gasoline exports
are unremarkable (*z* = −0.46).

**Diesel price exposure to Spain increased; gasoline's did not.** Short-run pass-through from
Spanish to Portuguese pre-tax diesel prices rises from 0.73 to approximately 1.01 across the
transition (interaction +0.2719, *p* < 0.001). The gasoline interaction is +0.0352 (*p* = 0.798),
indistinguishable from no change. Diesel is the product whose domestic manufacturing fell;
gasoline remained in domestic surplus throughout.

## What this does not claim

No causal effect of the closure is demonstrated. The Matosinhos transition and the European
energy shock fall fourteen months apart, and this design cannot separate their contributions.
Spain is a comparison series, not a causal control. The refinery-output-to-demand ratio is not
self-sufficiency: Portuguese output may be exported while domestic demand is met by imports,
which is the normal state for gasoline.

## Data coverage

JODI, Eurostat (PT and ES) and the EC Weekly Oil Bulletin cover 2005-2024 completely. **DGEG
product-trade workbooks cover only 2019-2024**, so the 2005-2018 cross-check runs against
Eurostat, which is compiled from the DGEG national submission rather than being independent of
it. DGEG domestic sales cover 1970-2024, so demand has three sources throughout.

See the Limitations section of the canonical report for the full list.

## Historical note

Earlier versions of this file, and the staged artifacts `data_audit.md`,
`interpretation_memo.md`, `peer_review.md` and `drafts/report_v1.md`, were written when the
evidence bundle was empty and correctly reported that no quantitative claim could be supported.
Those documents describe a repository state that no longer holds and are retained only as a
record of the review process.
