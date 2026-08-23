import math
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

from portugal_refining_resilience import prices as prices_module
from portugal_refining_resilience.prices import (
    _adjustment_speeds,
    ardl_bounds_test,
    choose_price_model,
    cointegrating_slope_test,
    cross_country_placebo,
    ecm_long_run_break_comparison,
    elasticity_unit_tests,
    extract_weekly_prices,
    false_break_placebo,
    fit_error_correction_model,
    gregory_hansen_test,
    joint_transition_wald_test,
    kpss_levels_diagnostics,
    placebo_joint_wald_test,
    post_period_adjustment_stability,
    price_comovement_design,
    regular_spacing_robustness,
    second_break_test,
    spread_stationarity,
    spread_stationarity_by_regime,
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
    design = pd.DataFrame({"log_PT": [1.0, 2.0], "log_ES": [1.0, 1.5]})

    out = choose_price_model(design, product="diesel")

    assert out["model_family"] == "insufficient_observations"
    assert out["n_obs"] == 2


def test_choose_price_model_requires_the_scale_it_licences() -> None:
    """The selector ran on EUR levels while both models were estimated in logs.

    The two disagreed: diesel Engle--Granger was 0.088 on levels and 0.022 on logs,
    which decided whether an ECM was fitted at all. Asking for the EUR columns must
    now fail rather than quietly answer a question about different series.
    """
    euro_only = pd.DataFrame({"PT": np.arange(40.0), "ES": np.arange(40.0)})

    with pytest.raises(ValueError, match="log_ES"):
        choose_price_model(euro_only, product="diesel")


def test_choose_price_model_diagnoses_the_same_columns_the_ecm_fits() -> None:
    """A structural guard: the selector and the model it licences share a scale."""
    design = pd.DataFrame(
        {
            "log_PT": np.linspace(0.0, 1.0, 40),
            "log_ES": np.linspace(0.0, 1.0, 40) + np.cos(np.arange(40.0)) * 0.1,
        }
    )

    out = choose_price_model(design, product="diesel")

    assert out["scale"] == "log"


@pytest.mark.parametrize(
    ("adf_p", "expected"),
    [(0.005, "levels"), (0.03, "ecm_required"), (0.20, "ecm_required")],
)
def test_choose_price_model_levels_branch_needs_one_percent(
    monkeypatch: pytest.MonkeyPatch, adf_p: float, expected: str
) -> None:
    """A marginal unit-root rejection must not licence a levels regression.

    Portuguese and Spanish log gasoline prices sit either side of five per cent
    depending only on the lag-selection rule, and the levels model reverses the sign
    of the post-transition interaction. The stricter threshold keeps that verdict
    from turning on an arbitrary choice.
    """
    monkeypatch.setattr(prices_module, "adfuller", lambda *a, **k: (0.0, adf_p, 1, 30))
    monkeypatch.setattr(prices_module, "coint", lambda *a, **k: (0.0, 0.001, None))
    design = pd.DataFrame(
        {"log_PT": np.linspace(0.0, 1.0, 40), "log_ES": np.linspace(1.0, 2.0, 40)}
    )

    out = choose_price_model(design, product="gasoline")

    assert out["model_family"] == expected


def _write_bulletin(
    path: Path, *, unit: str = "1000 l", countries: tuple[str, ...] = ("PT", "ES")
) -> Path:
    """Build a miniature Weekly Oil Bulletin workbook with the real layout."""
    dates = pd.date_range("2021-04-05", periods=4, freq="7D")
    sheets = {"wo": "Prices wo taxes", "with": "Prices with taxes"}
    with pd.ExcelWriter(path) as writer:
        for basis, sheet in sheets.items():
            headers: list[object] = ["Consumer prices"]
            units: list[object] = ["Date"]
            columns: list[list[object]] = [list(dates)]
            for country in countries:
                for token in ("euro95", "diesel"):
                    headers.append(f"{country}_price_{basis}_tax_{token}")
                    units.append(unit)
                    base = 1000.0 if basis == "wo" else 1600.0
                    columns.append([base + i for i in range(len(dates))])
            frame = pd.DataFrame(
                [
                    headers,
                    [None] * len(headers),
                    units,
                    *[list(row) for row in zip(*columns, strict=True)],
                ]
            )
            frame.to_excel(writer, sheet_name=sheet, header=False, index=False)
    return path


def test_extract_weekly_prices_returns_the_tidy_contract(tmp_path: Path) -> None:
    workbook = _write_bulletin(tmp_path / "bulletin.xlsx")

    tidy = extract_weekly_prices(workbook)

    assert list(tidy.columns) == [
        "date",
        "country",
        "product",
        "price_with_tax_eur_per_1000l",
        "price_without_tax_eur_per_1000l",
    ]
    assert set(tidy["country"]) == {"PT", "ES"}
    assert set(tidy["product"]) == {"diesel", "gasoline"}
    assert not tidy.duplicated(["date", "country", "product"]).any()
    assert tidy["price_without_tax_eur_per_1000l"].notna().all()


def test_extract_weekly_prices_rejects_an_unexpected_unit(tmp_path: Path) -> None:
    """A silently rebadged unit would feed the price models directly."""
    workbook = _write_bulletin(tmp_path / "bulletin.xlsx", unit="litre")

    with pytest.raises(ValueError, match="expected '1000 l'"):
        extract_weekly_prices(workbook)


def test_extract_weekly_prices_rejects_a_missing_country(tmp_path: Path) -> None:
    workbook = _write_bulletin(tmp_path / "bulletin.xlsx", countries=("PT",))

    with pytest.raises(ValueError, match="missing price columns"):
        extract_weekly_prices(workbook)


def _cointegrated_design(
    *, beta: float = 0.9, gamma: float = -0.25, theta: float = 0.6, n: int = 600
) -> pd.DataFrame:
    """A PT series that error-corrects toward a known long-run relation with ES."""
    rng = np.random.default_rng(7)
    log_es = np.cumsum(rng.normal(0, 0.02, n)) + np.log(1000.0)
    alpha = 0.5
    log_pt = np.empty(n)
    log_pt[0] = alpha + beta * log_es[0]
    for t in range(1, n):
        gap = log_pt[t - 1] - (alpha + beta * log_es[t - 1])
        log_pt[t] = (
            log_pt[t - 1] + gamma * gap + theta * (log_es[t] - log_es[t - 1]) + rng.normal(0, 0.004)
        )
    frame = pd.DataFrame({"date": pd.date_range("2015-01-04", periods=n, freq="7D")})
    frame["log_ES"] = log_es
    frame["log_PT"] = log_pt
    frame["diff_log_ES"] = frame["log_ES"].diff()
    frame["diff_log_PT"] = frame["log_PT"].diff()
    frame["post"] = (frame["date"] >= "2021-05-01").astype(int)
    return frame


def test_error_correction_model_recovers_the_cointegrating_vector() -> None:
    result = fit_error_correction_model(_cointegrated_design(beta=0.9))

    assert result["cointegrating_slope"] == pytest.approx(0.9, abs=0.03)


def test_error_correction_model_recovers_adjustment_and_pass_through() -> None:
    result = fit_error_correction_model(_cointegrated_design(gamma=-0.25, theta=0.6))
    model = result["model"]

    assert model.params["disequilibrium_lag"] == pytest.approx(-0.25, abs=0.06)
    assert model.params["disequilibrium_lag"] < 0  # a gap above the relation is pulled back
    assert model.pvalues["disequilibrium_lag"] < 0.01
    assert model.params["diff_log_ES"] == pytest.approx(0.6, abs=0.05)


def test_error_correction_model_finds_no_regime_change_when_there_is_none() -> None:
    """Both interactions must be flat when the process is stable across the cutoff."""
    result = fit_error_correction_model(_cointegrated_design())
    model = result["model"]

    assert model.pvalues["disequilibrium_lag_x_post"] > 0.05
    assert model.pvalues["diff_log_ES_x_post"] > 0.05


def test_error_correction_model_requires_the_design_columns() -> None:
    frame = pd.DataFrame({"log_PT": [1.0] * 30, "log_ES": [1.0] * 30})

    with pytest.raises(ValueError, match="Price design missing columns"):
        fit_error_correction_model(frame)


def test_error_correction_model_requires_enough_levels() -> None:
    frame = _cointegrated_design(n=600).head(15)

    with pytest.raises(ValueError, match="at least 20 paired price levels"):
        fit_error_correction_model(frame)


def _levels_frame(series_pt: np.ndarray, series_es: np.ndarray) -> pd.DataFrame:
    """Wrap two log-level paths in the columns the diagnostics read."""
    frame = pd.DataFrame({"log_PT": series_pt, "log_ES": series_es})
    frame["date"] = pd.date_range("2015-01-04", periods=len(frame), freq="7D")
    frame["post"] = (frame["date"] >= "2021-05-01").astype(int)
    return frame


def test_kpss_rejects_stationarity_for_a_random_walk() -> None:
    """The complement to ADF must call an integrated series integrated."""
    rng = np.random.default_rng(11)
    walk = np.cumsum(rng.normal(0, 0.02, 400)) + np.log(1000.0)
    frame = _levels_frame(walk, walk + rng.normal(0, 0.01, 400))

    result = kpss_levels_diagnostics(frame, product="diesel")

    assert set(result["regression"]) == {"c", "ct"}
    assert result.loc[result["regression"] == "c", "rejects_stationarity_5pct"].all()


def test_kpss_does_not_reject_stationarity_for_white_noise() -> None:
    """A test that rejected everything would settle nothing, so check the other branch."""
    rng = np.random.default_rng(12)
    noise = rng.normal(np.log(1000.0), 0.02, 400)
    frame = _levels_frame(noise, rng.normal(np.log(1000.0), 0.02, 400))

    result = kpss_levels_diagnostics(frame, product="diesel")

    assert not result.loc[result["regression"] == "c", "rejects_stationarity_5pct"].any()


def test_cointegrating_slope_test_recovers_a_slope_below_one() -> None:
    design = _cointegrated_design(beta=0.9)

    result = cointegrating_slope_test(design, product="diesel", leads_lags=(2, 4))

    assert set(result["leads_lags"]) == {2, 4}
    assert result["slope"].between(0.85, 0.95).all()
    assert result["differs_from_one_5pct"].all()


def test_cointegrating_slope_test_does_not_reject_a_unit_slope() -> None:
    """The whole point of the test is that it can come out either way."""
    design = _cointegrated_design(beta=1.0)

    result = cointegrating_slope_test(design, product="diesel", leads_lags=(2,))

    assert result["slope"].iloc[0] == pytest.approx(1.0, abs=0.03)
    assert not bool(result["differs_from_one_5pct"].iloc[0])


def test_elasticity_unit_tests_place_the_estimate_against_one() -> None:
    design = _cointegrated_design(theta=0.6)

    result = elasticity_unit_tests(design, product="diesel")

    pre = result.loc[result["phase"] == "pre_transition"].iloc[0]
    assert pre["elasticity"] == pytest.approx(0.6, abs=0.06)
    assert pre["side"] == "below"
    assert pre["t_statistic_vs_one"] < 0
    assert bool(pre["differs_from_one_5pct"])


def test_post_period_stability_reports_the_full_sample_among_the_subsets() -> None:
    """The subset rows are only interpretable next to the estimate they qualify."""
    design = _cointegrated_design(gamma=-0.25)
    full = fit_error_correction_model(design)
    model = full["model"]
    expected = float(model.params["disequilibrium_lag"] + model.params["disequilibrium_lag_x_post"])

    result = post_period_adjustment_stability(design, product="diesel")

    assert set(result["subset"]) == {
        "full_post_period",
        "excluding_2022",
        "first_half_of_post",
        "second_half_of_post",
    }
    row = result.loc[result["subset"] == "full_post_period"].iloc[0]
    assert row["post_adjustment_speed"] == pytest.approx(expected, abs=1e-9)
    assert (result["n_post"] > 0).all()


def test_spread_stationarity_by_regime_splits_at_the_transition() -> None:
    """A pooled test on a series whose mean shifts is the one result not to quote."""
    rng = np.random.default_rng(13)
    frame = pd.DataFrame({"date": pd.date_range("2015-01-04", periods=400, freq="7D")})
    frame["post"] = (frame["date"] >= "2021-05-01").astype(int)
    frame["ES"] = 1000.0 + rng.normal(0, 5, 400)
    # a stationary spread whose level moves across the transition
    frame["PT"] = frame["ES"] + rng.normal(0, 3, 400) - 40.0 * frame["post"]

    result = spread_stationarity_by_regime(frame, product="diesel")

    assert list(result["segment"]) == ["pooled", "pre_transition", "post_transition"]
    pre = result.loc[result["segment"] == "pre_transition"].iloc[0]
    post = result.loc[result["segment"] == "post_transition"].iloc[0]
    assert post["mean_spread"] < pre["mean_spread"] - 30.0
    assert bool(pre["stationary_5pct"]) and bool(post["stationary_5pct"])


def test_spread_stationarity_by_regime_requires_the_price_columns() -> None:
    frame = pd.DataFrame({"log_PT": [1.0] * 30, "log_ES": [1.0] * 30})

    with pytest.raises(ValueError, match="Price design missing columns"):
        spread_stationarity_by_regime(frame, product="diesel")


def _dated(frame: pd.DataFrame) -> pd.DataFrame:
    """The regime tests key on real dates, so give a synthetic design some."""
    out = frame.copy()
    if "date" not in out.columns:
        out["date"] = pd.date_range("2015-01-04", periods=len(out), freq="7D")
    out["PT"] = np.exp(out["log_PT"])
    out["ES"] = np.exp(out["log_ES"])
    return out


def test_gregory_hansen_finds_cointegration_when_it_is_there() -> None:
    design = _dated(_cointegrated_design(n=400))

    result = gregory_hansen_test(design, product="diesel", step=10, n_simulations=60, seed=1)

    assert len(result) == 1
    assert bool(result["cointegrated_with_shift_5pct"].iloc[0])
    assert result["adf_statistic"].iloc[0] < result["null_5th_percentile"].iloc[0]


def test_gregory_hansen_does_not_find_cointegration_between_independent_walks() -> None:
    """A test that rejected for any pair of trending series would establish nothing."""
    rng = np.random.default_rng(4)
    n = 200
    frame = pd.DataFrame(
        {
            "log_PT": np.cumsum(rng.normal(0, 0.02, n)) + np.log(1000.0),
            "log_ES": np.cumsum(rng.normal(0, 0.02, n)) + np.log(1000.0),
        }
    )
    frame["post"] = 0
    design = _dated(frame)

    result = gregory_hansen_test(design, product="diesel", step=10, n_simulations=40, seed=2)

    assert not bool(result["cointegrated_with_shift_5pct"].iloc[0])


def test_gregory_hansen_requires_enough_observations() -> None:
    design = _dated(_cointegrated_design(n=200)).head(40)

    with pytest.raises(ValueError, match="at least 60 paired observations"):
        gregory_hansen_test(design, product="diesel", n_simulations=5)


def test_second_break_test_reports_no_break_when_there_is_none() -> None:
    design = _dated(_cointegrated_design(n=600))

    result = second_break_test(design, product="diesel", second_cutoff="2022-03-01")

    assert not bool(result["second_break_detected_5pct"].iloc[0])
    assert float(result["joint_p_value"].iloc[0]) > 0.05


def test_second_break_test_records_each_regime_level() -> None:
    """The paper quotes regime levels, so they have to exist as rows, not as arithmetic."""
    design = _dated(_cointegrated_design(n=600))

    result = second_break_test(design, product="diesel", second_cutoff="2022-03-01")
    terms = set(result["term"])

    for name in (
        "elasticity_pre_closure",
        "elasticity_transition",
        "elasticity_stress_onward",
        "adjustment_pre_closure",
        "adjustment_transition",
        "adjustment_stress_onward",
    ):
        assert name in terms
    pre = result.loc[result["term"] == "elasticity_pre_closure", "estimate"].iloc[0]
    assert pre == pytest.approx(0.6, abs=0.08)


def test_second_break_test_requires_the_design_columns() -> None:
    frame = pd.DataFrame({"log_PT": [1.0] * 40, "log_ES": [1.0] * 40})

    with pytest.raises(ValueError, match="Price design missing columns"):
        second_break_test(frame, product="diesel")


def _placebo_panel(seed: int = 21) -> pd.DataFrame:
    """A long panel of several countries priced against Spain, only one of which breaks."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2015-01-04", periods=400, freq="7D")
    post = (dates >= pd.Timestamp("2021-05-01")).astype(float)
    log_es = np.cumsum(rng.normal(0, 0.02, len(dates))) + np.log(1000.0)
    frames = []
    for country, gamma_pre, gamma_post in (
        ("PT", -0.15, -0.60),
        ("FR", -0.20, -0.20),
        ("IT", -0.25, -0.25),
    ):
        log_home = np.empty(len(dates))
        log_home[0] = 0.2 + log_es[0]
        for t in range(1, len(dates)):
            gamma = gamma_post if post[t] else gamma_pre
            gap = log_home[t - 1] - (0.2 + log_es[t - 1])
            log_home[t] = (
                log_home[t - 1]
                + gamma * gap
                + 0.7 * (log_es[t] - log_es[t - 1])
                + rng.normal(0, 0.004)
            )
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "country": country,
                    "product": "diesel",
                    "price_without_tax_eur_per_1000l": np.exp(log_home),
                }
            )
        )
    frames.append(
        pd.DataFrame(
            {
                "date": dates,
                "country": "ES",
                "product": "diesel",
                "price_without_tax_eur_per_1000l": np.exp(log_es),
            }
        )
    )
    return pd.concat(frames, ignore_index=True)


def test_cross_country_placebo_separates_the_pair_that_broke() -> None:
    result = cross_country_placebo(_placebo_panel(), countries=("FR", "IT"))

    assert set(result["pair"]) == {"PT-ES", "FR-ES", "IT-ES"}
    portugal = result.loc[result["pair"] == "PT-ES"].iloc[0]
    controls = result.loc[result["pair"] != "PT-ES"]

    assert bool(portugal["closed_a_refinery"])
    assert not controls["closed_a_refinery"].any()
    assert portugal["speed_ratio"] > 2.0
    assert (controls["speed_ratio"] < 2.0).all()
    assert portugal["interaction_p_value"] < 0.01


def test_false_break_placebo_marks_the_real_break_and_ends_the_others_early() -> None:
    """A false break tested on the full sample would recover the real one and prove nothing."""
    result = false_break_placebo(
        _placebo_panel(), dates=("2017-05-01", "2019-05-01"), real_break="2021-05-01"
    )

    assert len(result) == 3
    real = result.loc[result["is_real_break"]].iloc[0]
    false = result.loc[~result["is_real_break"]]

    assert real["break_date"] == "2021-05-01"
    assert (false["sample_ends"] == "2021-05-01").all()
    # the false breaks see fewer observations precisely because the sample is cut short
    assert (false["n_obs"] < real["n_obs"]).all()
    assert real["speed_ratio"] > false["speed_ratio"].max()


def _cointegrated_pair(n: int = 400, seed: int = 7, shift_size: float = 0.05) -> pd.DataFrame:
    """A PT-ES pair that shares a stochastic trend, with a level shift part way through."""
    rng = np.random.default_rng(seed)
    common = np.cumsum(rng.normal(0, 0.01, n)) + np.log(1200.0)
    shift = np.where(np.arange(n) >= n // 2, shift_size, 0.0)
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2005-01-03", periods=n, freq="7D"),
            "ES": np.exp(common),
            "PT": np.exp(common + shift + rng.normal(0, 0.004, n)),
        }
    )
    long = frame.melt("date", var_name="country", value_name="price_without_tax_eur_per_1000l")
    long["product"] = "diesel"
    return long


def test_long_run_break_changes_the_disequilibrium_but_not_the_default() -> None:
    """Passing no break must reproduce the fixed-vector fit exactly."""
    design = price_comovement_design(_cointegrated_pair(), product="diesel", cutoff="2010-01-01")
    plain = fit_error_correction_model(design)
    same = fit_error_correction_model(design, long_run_break=None)
    assert plain["cointegrating_slope"] == same["cointegrating_slope"]
    assert math.isnan(cast(float, plain["long_run_level_shift"]))

    shifted = fit_error_correction_model(design, long_run_break="2008-01-01")
    assert shifted["long_run_break"] == "2008-01-01"
    assert not math.isnan(cast(float, shifted["long_run_level_shift"]))
    assert shifted["cointegrating_slope"] != plain["cointegrating_slope"]


def test_ecm_long_run_break_comparison_reports_both_specifications() -> None:
    design = price_comovement_design(_cointegrated_pair(), product="diesel", cutoff="2010-01-01")
    out = ecm_long_run_break_comparison(design, product="diesel", long_run_break="2008-01-01")
    assert list(out["specification"]) == [
        "fixed long-run vector",
        "long-run vector shifts at the estimated date",
    ]
    assert out.loc[0, "long_run_break"] == ""
    assert out.loc[1, "long_run_break"] == "2008-01-01"
    assert (out["post_adjustment_speed"] != out["pre_adjustment_speed"]).all()


def test_ardl_bounds_test_finds_a_level_relationship_in_a_cointegrated_pair() -> None:
    """No level shift here: an unmodelled shift is exactly what should defeat the test."""
    pair = _cointegrated_pair(shift_size=0.0)
    design = price_comovement_design(pair, product="diesel", cutoff="2010-01-01")
    result = ardl_bounds_test(design, product="diesel")
    assert result["level_relationship_5pct"] is True
    assert result["p_value_upper_bound"] < 0.05
    assert result["statistic"] > 0


def test_regular_spacing_robustness_drops_only_irregular_differences() -> None:
    """A gap makes one difference span two weeks; the seven-day fit must exclude it."""
    prices = _cointegrated_pair()
    dropped_date = prices["date"].unique()[100]
    prices = prices.loc[prices["date"] != dropped_date]
    design = price_comovement_design(prices, product="diesel", cutoff="2010-01-01")

    out = regular_spacing_robustness(design, product="diesel")
    assert list(out["sample"]) == ["all observations", "seven-day gaps only"]
    assert out.loc[1, "dropped"] == 1.0
    assert out.loc[1, "nobs"] < out.loc[0, "nobs"]


def test_adjustment_speeds_record_whether_an_ecm_is_licensed() -> None:
    """The placebo quoted speeds for pairs whose levels the same gate declines."""
    prices = _cointegrated_pair()
    prices["country"] = prices["country"].replace({"PT": "IT"})
    speeds = _adjustment_speeds(prices, home="IT", product="diesel", cutoff="2010-01-01")
    assert "ecm_licensed" in speeds
    assert "cointegration_p_value" in speeds
    assert isinstance(speeds["ecm_licensed"], bool)


def test_joint_transition_test_uses_every_transition_term() -> None:
    """One hypothesis with three restrictions, not three hypotheses."""
    design = price_comovement_design(_cointegrated_pair(), product="diesel", cutoff="2010-01-01")
    result = joint_transition_wald_test(design, product="diesel")

    assert result["df_num"] == len(prices_module.TRANSITION_TERMS) == 3
    assert result["specification"] == "fixed long-run vector"
    assert 0.0 <= float(cast(float, result["p_value"])) <= 1.0
    assert float(cast(float, result["f_statistic"])) >= 0.0


def test_joint_transition_test_reports_the_specification_it_used() -> None:
    design = price_comovement_design(_cointegrated_pair(), product="diesel", cutoff="2010-01-01")
    shifted = joint_transition_wald_test(design, product="diesel", long_run_break="2008-01-01")
    assert shifted["specification"] == "long-run vector shifts at the estimated date"


def test_placebo_joint_test_covers_only_licensed_pairs() -> None:
    """A pair the diagnostics decline must not enter the joint restriction."""
    rng = np.random.default_rng(11)
    frames = []
    for country, cointegrated in (("FR", True), ("IT", False)):
        pair = _cointegrated_pair(seed=3, shift_size=0.0)
        if not cointegrated:
            # give this one an independent walk, so it shares no equilibrium with ES
            wandering = pair["country"].eq("PT")
            pair.loc[wandering, "price_without_tax_eur_per_1000l"] = np.exp(
                np.cumsum(rng.normal(0, 0.02, int(wandering.sum()))) + np.log(1200.0)
            )
        pair = pair.loc[pair["country"] != "ES"] if country != "FR" else pair
        pair["country"] = pair["country"].replace({"PT": country})
        frames.append(pair)

    panel = pd.concat(frames, ignore_index=True)
    result = placebo_joint_wald_test(
        panel, product="diesel", cutoff="2010-01-01", countries=("FR", "IT")
    )
    assert "IT-ES" not in str(result["pairs"])
    assert result["df_num"] == len(str(result["pairs"]).split(",")) if result["pairs"] else True


def test_placebo_joint_test_returns_an_empty_verdict_without_licensed_pairs() -> None:
    panel = _cointegrated_pair()
    result = placebo_joint_wald_test(
        panel, product="diesel", cutoff="2010-01-01", countries=("XX",)
    )
    assert result["pairs"] == ""
    assert result["nobs"] == 0
    assert result["rejected_5pct"] is False
