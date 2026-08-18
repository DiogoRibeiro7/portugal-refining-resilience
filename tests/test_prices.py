import numpy as np
import pandas as pd

from portugal_refining_resilience.prices import (
    choose_price_model,
    price_comovement_design,
    spread_stationarity,
    stationarity_diagnostics,
)


def test_price_comovement_design_adds_interaction_and_differences() -> None:
    dates = pd.date_range("2021-04-25", periods=4, freq="W")
    prices = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "country": ["PT"] * 4 + ["ES"] * 4,
            "product": ["diesel"] * 8,
            "price_without_tax_eur_per_1000l": [101, 102, 103, 104, 100, 100, 110, 110],
        }
    )

    out = price_comovement_design(prices, product="diesel", cutoff="2021-05-02")

    assert out.loc[0, "post"] == 0
    assert out.loc[1, "post"] == 1
    assert out.loc[1, "ES_x_post"] == out.loc[1, "ES"]
    assert np.isfinite(out.loc[1, "diff_log_PT"])


def test_stationarity_diagnostics_handles_short_series() -> None:
    frame = pd.DataFrame({"product": ["diesel"] * 3, "value": [1.0, 2.0, 3.0]})

    out = stationarity_diagnostics(
        frame, value_column="value", group_columns=["product"], min_observations=10
    )

    assert out.loc[0, "status"] == "insufficient_observations"
    assert bool(out.loc[0, "stationary_5pct"]) is False


def test_spread_stationarity_handles_short_design() -> None:
    design = pd.DataFrame({"PT": [1.0, 2.0], "ES": [1.0, 1.5]})

    out = spread_stationarity(design)

    assert out["status"] == "insufficient_observations"


def test_choose_price_model_handles_short_design() -> None:
    design = pd.DataFrame({"PT": [1.0, 2.0], "ES": [1.0, 1.5]})

    out = choose_price_model(design, product="diesel")

    assert out["model_family"] == "insufficient_observations"
    assert out["n_obs"] == 2
