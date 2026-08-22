import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from portugal_refining_resilience.breaks import (
    andrews_sup_wald,
    chow_test,
    coefficient_table,
    global_break_search,
    interrupted_time_series,
    residual_diagnostics,
)


def test_chow_detects_large_known_level_break() -> None:
    years = pd.Series(range(2005, 2025))
    values = pd.Series(
        [year - 2000 for year in range(2005, 2015)]
        + [100 + year - 2015 for year in range(2015, 2025)]
    )
    result = chow_test(years, values, break_year=2015)
    assert np.isfinite(result.f_statistic)
    assert result.p_value < 0.05


def test_chow_excludes_transition_years() -> None:
    years = pd.Series(range(2005, 2025))
    values = pd.Series(range(20))
    result = chow_test(years, values, break_year=2022, transition_years=(2021,))
    assert result.excluded_years == (2021,)
    assert result.n_pre == 16
    assert result.n_post == 3


def _trending_panel(break_year: int | None, *, jump: float = 0.0, seed: int = 3) -> pd.DataFrame:
    """An annual series with a trend and, optionally, one level shift."""
    rng = np.random.default_rng(seed)
    years = np.arange(1990, 2025)
    values = 100.0 + 2.0 * (years - 1990) + rng.normal(0.0, 4.0, len(years))
    if break_year is not None:
        values = values + jump * (years >= break_year)
    return pd.DataFrame({"year": years, "value": values})


def test_sup_wald_finds_a_break_it_was_not_told_about() -> None:
    result = andrews_sup_wald(_trending_panel(2005, jump=120.0), value_column="value")

    assert result.p_value < 0.05
    assert abs(result.break_year - 2005) <= 1


def test_sup_wald_does_not_invent_a_break_in_a_clean_trend() -> None:
    """Searching every candidate year finds a maximum in any series; it must not reject on one."""
    result = andrews_sup_wald(_trending_panel(None), value_column="value")

    assert result.p_value > 0.05
    assert result.statistic <= result.null_95th_percentile


def test_sup_wald_needs_enough_observations() -> None:
    with pytest.raises(ValueError, match="at least 12 observations"):
        andrews_sup_wald(_trending_panel(None).head(8), value_column="value")


def test_interrupted_trend_control_event_recovers_the_later_shift() -> None:
    """With two shifts, ignoring the earlier one biases the estimate of the later one."""
    rng = np.random.default_rng(5)
    years = np.arange(1990, 2025)
    values = (
        100.0
        + 2.0 * (years - 1990)
        + 300.0 * (years >= 2005)
        - 80.0 * (years >= 2018)
        + rng.normal(0.0, 5.0, len(years))
    )
    frame = pd.DataFrame({"year": years, "value": values})

    naive = interrupted_time_series(frame, value_column="value", event_year=2018)
    controlled = interrupted_time_series(
        frame, value_column="value", event_year=2018, control_events=(2005,)
    )

    assert abs(float(controlled.params["post"]) - (-80.0)) < abs(
        float(naive.params["post"]) - (-80.0)
    )
    assert "post_2005" in controlled.params.index
    assert "post_2005" not in naive.params.index


def test_interrupted_trend_ignores_a_control_equal_to_the_event() -> None:
    frame = _trending_panel(2010, jump=50.0)
    model = interrupted_time_series(
        frame, value_column="value", event_year=2010, control_events=(2010,)
    )

    assert "post_2010" not in model.params.index


def test_residual_diagnostics_flag_autocorrelation() -> None:
    """A trend fitted through an unmodelled level shift leaves autocorrelated residuals."""
    frame = _trending_panel(2005, jump=200.0)
    x = sm.add_constant(frame[["year"]], has_constant="add")
    model = sm.OLS(frame["value"], x).fit()

    record = residual_diagnostics(model, label="misspecified")

    assert record["model"] == "misspecified"
    assert record["durbin_watson"] < 1.5
    assert record["residual_autocorrelation_5pct"] is True


def test_coefficient_table_brackets_the_estimate() -> None:
    frame = _trending_panel(None)
    x = sm.add_constant(frame[["year"]], has_constant="add")
    model = sm.OLS(frame["value"], x).fit()

    table = coefficient_table(model, outcome="value")

    assert set(table["term"]) == {"const", "year"}
    assert (table["ci_low"] < table["estimate"]).all()
    assert (table["estimate"] < table["ci_high"]).all()
    assert (table["ci_level"] == 0.95).all()
    assert (table["outcome"] == "value").all()


def test_global_break_search_finds_a_planted_break() -> None:
    rng = np.random.default_rng(31)
    years = np.arange(1990, 2025)
    values = 100.0 + 2.0 * (years - 1990) + 150.0 * (years >= 2008) + rng.normal(0, 4.0, len(years))
    frame = pd.DataFrame({"year": years, "value": values})

    table = global_break_search(frame, value_column="value", max_breaks=2)

    chosen = table.loc[table["selected_by_bic"]].iloc[0]
    assert chosen["n_breaks"] >= 1
    assert "2008" in str(chosen["break_years"])


def test_global_break_search_prefers_no_break_in_a_clean_trend() -> None:
    """BIC has to be able to return zero, or the search always finds structure."""
    rng = np.random.default_rng(32)
    years = np.arange(1990, 2025)
    values = 100.0 + 2.0 * (years - 1990) + rng.normal(0, 4.0, len(years))
    frame = pd.DataFrame({"year": years, "value": values})

    table = global_break_search(frame, value_column="value", max_breaks=2)

    assert int(table.loc[table["selected_by_bic"], "n_breaks"].iloc[0]) == 0


def test_global_break_search_reports_the_years_it_could_not_reach() -> None:
    """A date inside the trimmed region cannot be selected, and the caller must be told."""
    rng = np.random.default_rng(33)
    years = np.arange(1990, 2025)
    frame = pd.DataFrame({"year": years, "value": 100.0 + rng.normal(0, 4.0, len(years))})

    table = global_break_search(frame, value_column="value", max_breaks=1, min_segment=5)

    assert int(table["earliest_candidate"].iloc[0]) == 1995
    assert int(table["latest_candidate"].iloc[0]) == 2019


def test_global_break_search_needs_enough_observations() -> None:
    frame = pd.DataFrame({"year": np.arange(2000, 2012), "value": np.arange(12.0)})

    with pytest.raises(ValueError, match="at least 20 observations"):
        global_break_search(frame, value_column="value", min_segment=5)
