# Canonical data contracts

## `fuel_trade_annual.csv`

Key: `year, product, flow`

Required: `year`, `product ∈ {diesel, gasoline}`, `flow ∈ {imports, exports}`, `value_kt`, `source`, `status`.

Numerical reconciliation across sources must use only product definitions marked comparable in
`data/reference/product_definition_crosswalk.csv`.

## `fuel_demand_annual.csv`

Key: `year, product`

Required: `year`, `product`, `demand_kt`, `source`.

## `fuel_refinery_output_annual.csv`

Key: `year, product`

Required: `year`, `product`, `refinery_output_kt`, `refining_regime`.

## `weekly_oil_prices_tidy.csv`

Key: `date, country, product`

Required countries: Portugal and Spain. Required products: diesel and gasoline. Required primary price: `price_without_tax_eur_per_1000l`. After-tax price should be retained separately.

## `fuel_annual_analytical_panel.csv`

Key: `year, product`.

No missing physical quantity may be replaced with zero unless the source definition explicitly establishes a true zero.

## `fuel_monthly_analytical_panel.csv`

Key: `date, product`.

Required: `date`, `year`, `month`, `product`, `event_phase`, and the available monthly physical quantities among `imports_kt`, `exports_kt`, `demand_kt`, and `refinery_output_kt`.

`event_phase` must distinguish at least:

- `pre_matosinhos_closure` before May 2021;
- `matosinhos_transition` from May 2021 through February 2022;
- `energy_stress_2022` from March 2022 through December 2022;
- `post_stress` from January 2023 onward.

Monthly event-timing claims about Matosinhos versus the 2022 energy shock must use this table or a stricter saved model artifact.

## `monthly_event_phase_summary.csv`

Key: `product, outcome, event_phase`.

Required: `product`, `outcome`, `event_phase`, `n_months`, `mean_value`, and `std_value`.

## `monthly_event_models.csv`

Key: `product, outcome, term`.

Required: `product`, `outcome`, `term`, `estimate`, `std_error`, `p_value`, and `n_obs`.

The fitted design must include month fixed effects, a linear time trend, phase indicators for
`matosinhos_transition`, `energy_stress_2022`, and `post_stress`, and phase-trend interactions.
Claims that isolate the Matosinhos transition from the 2022 energy shock must cite these saved
coefficients rather than informal visual inspection.

The time trend is measured in elapsed calendar months, so a gap in the monthly series does not
rescale it. Each phase-trend interaction is centred on that phase's first observed month. A phase
indicator is therefore the level shift at that phase boundary, measured against the extrapolated
pre-closure trend, and its `*_trend` companion is the change in slope within the phase. Both terms
must be quoted together: neither is the whole effect on its own, and the level term is not a
cumulative post-event average.

## `jodi_dgeg_trade_reconciliation.csv`

Key: `year, product, flow`.

Required: the primary and comparison `value_kt` columns, `difference_kt`,
`difference_pct_comparison`, and `reconciliation_status`.

JODI and DGEG are the only independent pair available for Portuguese product trade.
Eurostat `nrg_cb_oil` is compiled from the DGEG national submission and agrees with it to a
median of 0.00% across 2019-2024 trade cells, so it corroborates DGEG rather than supplying a
third opinion. It is still useful as an adjudicator: where JODI and DGEG disagree, Eurostat
indicates which of the two is out of line.

A row is flagged `review` only when it breaches **both** the absolute and the percentage
tolerance. Treating them as alternatives made the 25 kt floor bind on every large series,
giving an effective tolerance of 1.6% on Portuguese diesel imports and flagging agreement as
close as 2.1% as a failure.

Differing product definitions are not the source of the residual gap. The Eurostat blended
biofuel wedge (`O4671` less `O4671XR5220B`) is 0.0 kt on exports in every year and at most
4.5% on imports, so blending cannot explain export divergences at all.

Every remaining `review` row must be listed in `config/analysis.yml` under
`analysis.source_reconciliation.accepted_divergences`, with the series Eurostat identifies as
the outlier. An unlisted divergence fails the readiness gate however few cells it touches, so
a new data vintage cannot quietly widen the gap. Separately, at least
`min_within_tolerance_share` of all rows must agree without invoking an exception, so the
exception list can never grow until it carries the comparison.

## `price_ecm_models.csv`

Key: `product, term`.

Required: `product`, `term`, `estimate`, `std_error`, `p_value`, `nobs`,
`cointegrating_constant`, `cointegrating_slope`.

Written only for products whose `price_model_choice.model_family` is `ecm_required`. Where
cointegration is rejected the disequilibrium term is not a valid long-run residual, so fitting
an error-correction model anyway would contradict the recorded model choice.

`disequilibrium_lag` is the weekly speed of adjustment toward the long-run relation and is
expected to be negative. Its `_x_post` companion is the change in that speed after the
transition; quote the two together. The disequilibrium term is a generated regressor, so the
second-stage standard errors are conditional on the first stage.

## `eurostat_physical_balance_panel.csv`

Key: `year, country, product`.

Required where available: imports, exports, demand, refinery output, balance residual, and the ratio columns used for Portugal-Spain comparison.

## `price_stationarity_diagnostics.csv`

Key: `country, product, value_column`.

Required before interpreting weekly price-level co-movement regressions.

## `price_model_choice.csv`

Key: `product`.

Required: `product`, `model_family`, and `reason`.

The model family must record whether the price analysis is using stationary levels, requires an
ECM because levels appear cointegrated, or falls back to short-run log differences.
