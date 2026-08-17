# Canonical data contracts

## `fuel_trade_annual.csv`

Key: `year, product, flow`

Required: `year`, `product ∈ {diesel, gasoline}`, `flow ∈ {imports, exports}`, `value_kt`, `source`, `status`.

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
