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
