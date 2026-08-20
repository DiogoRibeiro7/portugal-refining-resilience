# From Refining Capacity to Import Dependence: Portugal's Diesel and Gasoline Market, 1990-2024

**The canonical report is [`report_final.tex`](report_final.tex)**, built with `make report-pdf`.
This file is a summary; where the two differ, the LaTeX source is authoritative. Every figure below
is verified against the evidence bundle by the claim checks described in
[`data_provenance.md`](data_provenance.md).

## Windows

Each arm runs over the study window intersected with what its own source provides.

| Arm | Window | Limited by |
| --- | --- | --- |
| Annual physical balance | 1990-2024 | Eurostat, earliest published year |
| Monthly event models | 2002-2024 (n = 276) | JODI, earliest published month |
| Weekly price models | 2005-2024 (n = 1,078) | EC Weekly Oil Bulletin |

## What "resilience" means here

Four senses, each tied to a quantity: the **domestic buffer** (refinery output over demand),
**import exposure** (imports over demand, and the net position), **concentration** (two refineries
to one), and **price integration** (co-movement with Spain, and how fast a gap closes). The
profile moved on all four, in the same direction.

Not measured, and this bounds every claim: stocks, storage and port capacity, supplier
diversification, crude slate, and the terms on which the extra imports were obtained. Rising
import dependence is not by itself evidence of reduced security of supply.

## Headline findings

**The system crossed the same line three times.** Portugal was a net diesel exporter through most
of the 1990s, a net importer for the fourteen years from 1999, an exporter again from 2013 after
the hydrocracker, and an importer in every year since 2021. The 2013 unit did not move Portugal
somewhere new — it restored the position the country had held in the early 1990s. The 2021 closure
did not merely undo that: 2023 is the most import-dependent year in the whole window.

**Three transitions, not one.** Portuguese refinery output breaks upward around 2000 for both
products, most strongly for gasoline (*F* = 22.0, Benjamini-Hochberg adjusted *p* < 0.001). Neither
ratio breaks there: output and imports rose because demand rose faster, so the system was expanding
rather than changing character. **This break is exploratory** — it was added after the panel was
extended to 1990 and was not pre-specified.

**The 2013 hydrocracker is the sharp one.** Diesel exports and the net-import-to-demand ratio both
break at 2013 (adjusted *p* < 0.001), and Portugal moved from net diesel importer to net diesel
exporter. Six of twenty-four Chow tests survive multiplicity adjustment.

**After May 2021 the direction reverses.** By 2023 domestic manufacturing covered 0.68 of diesel
demand, the lowest in the window, with imports at a series high of 1,632 kt.

**The monthly design separates the closure from the 2022 shock**, which annual data cannot do with
ten months between them:

Each phase is measured against the same counterfactual — the pre-closure trend extrapolated
forward — not against the phase before it, so the second column is not an increment on the first:

| Outcome, vs pre-closure counterfactual | Matosinhos transition | Energy stress 2022 |
| --- | --- | --- |
| Refinery output | −103 kt/month (*p* = 0.005) | −148 kt/month (*p* < 0.001) |
| Net imports / demand | +0.19 (*p* = 0.007) | +0.37 (*p* < 0.001) |

**The annual 2022 evidence is weaker than a short window suggests.** Fitted from 1990 against a
trend informed by the 1990s, the diesel export level shift is −782 kt (*p* = 0.022), roughly half
what a 2005-start window gives, and both gasoline shifts lose significance.

**Spain did not move the same way.** Over 2018-2024 Spanish diesel output covered 0.85-0.93 of
Spanish demand with no trend, while Portugal's fell to 0.678 in 2023 against Spain's 0.923. That
weakens a purely common-shock account without disposing of it. The comparison is confined to
those years on purpose: across the full 1990-2024 panel the Spanish ratio is not flat either,
falling to 0.667 in 2007 before recovering.

**Price linkage tightened for both fuels.** Both pairs are cointegrated in log prices, so both get
an error-correction model, and both adjustment speeds more than triple after the transition:

| Product | Adjustment speed | Half-life of a gap | Contemporaneous elasticity |
| --- | --- | --- | --- |
| Diesel | −0.133 → −0.466 | 4.9 → 1.1 weeks | 0.713 → 1.242 (*p* < 0.001) |
| Gasoline | −0.091 → −0.315 | 7.3 → 1.8 weeks | 0.789 → 0.994 (*p* = 0.218) |

The channels differ: diesel tightened in both, gasoline only in the speed of adjustment. The
diagnostics are run on log prices, the scale the models are estimated on. On the EUR/1000L levels
diesel does not appear cointegrated (*p* = 0.088 against 0.022 on logs), which would have replaced
the diesel model with a difference-only one and put its post-transition elasticity at 1.01.

## What this does not claim

No causal effect of the closure is demonstrated. The Matosinhos transition and the European energy
shock fall ten months apart and this design cannot separate them. Spain is a comparison series, not
a control.

The price results are **co-movement, not pass-through**. The specification regresses one price
change on another with no control for the common wholesale cost, crude, exchange-rate or policy
movements that drive both. An elasticity near one says the markets move together almost one for
one; it does not establish that Spanish prices transmit to Portuguese ones.

The refinery-output-to-demand ratio is not self-sufficiency: output may be exported while domestic
demand is met by imports, which is the normal state for gasoline.

## Data coverage

JODI, Eurostat for both countries, and the price bulletin cover their windows completely. **DGEG
product-trade workbooks reach back only to 2019**, so the earlier cross-check runs against
Eurostat, which is compiled from the DGEG submission rather than independent of it. DGEG sales
corroborates demand across the whole window at a median absolute difference of 0.9%.

The annual panel is built from Eurostat, the only source reaching back to 1990. One consequence is
that the two 2022 trade cells the reconciliation flags do not enter the annual arm at all, since
the national submission already carries the corroborated values.

See the Limitations section of the canonical report for the full list.

## Superseded material

The staged artifacts from the report-writing chain — `data_audit.md`, `interpretation_memo.md`,
`peer_review.md` and `report_v1.md` — were written when the evidence bundle was empty and correctly
reported that no quantitative claim could be supported. They describe a repository state that has
not held for many commits, and their headline numbers do not match this report. They are kept in
[`archive/`](archive/) as a record of the review process, not as current findings.
