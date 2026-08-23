import numpy as np
import pandas as pd
import pytest

from portugal_refining_resilience.events import (
    annual_event_role,
    assign_monthly_event_phase,
    fit_monthly_event_model,
    monthly_phase_summary,
    phase_contrasts,
)


def test_assign_monthly_event_phase_separates_closure_and_2022_stress() -> None:
    dates = pd.Series(pd.to_datetime(["2021-04-01", "2021-05-01", "2022-03-01", "2023-01-01"]))

    out = assign_monthly_event_phase(dates)

    assert out.tolist() == [
        "pre_matosinhos_closure",
        "matosinhos_transition",
        "energy_stress_2022",
        "post_stress",
    ]


def test_assign_monthly_event_phase_does_not_call_an_undated_row_pre_closure() -> None:
    """Every comparison against NaT is False, so the default label used to win.

    An undated observation would have been counted as pre-closure evidence, which is
    the phase the whole design contrasts everything else against.
    """
    dates = pd.Series(pd.to_datetime(["2021-04-01", None, "2022-03-01"]))

    out = assign_monthly_event_phase(dates)

    assert out.tolist()[0] == "pre_matosinhos_closure"
    assert out.isna().tolist() == [False, True, False]


def test_annual_event_role_keeps_2021_as_transition() -> None:
    years = pd.Series([2020, 2021, 2022])

    out = annual_event_role(years)

    assert out.tolist() == ["pre_transition", "transition", "post_transition"]


def test_monthly_phase_summary_groups_outcomes_by_phase() -> None:
    frame = pd.DataFrame(
        {
            "product": ["diesel", "diesel", "diesel"],
            "event_phase": [
                "pre_matosinhos_closure",
                "pre_matosinhos_closure",
                "energy_stress_2022",
            ],
            "imports_kt": [10.0, 14.0, 20.0],
        }
    )

    out = monthly_phase_summary(frame, value_column="imports_kt")

    pre = out.loc[out["event_phase"].eq("pre_matosinhos_closure")].iloc[0]
    assert pre["n_months"] == 2
    assert pre["mean_value"] == 12.0


def test_monthly_phase_summary_emits_only_contract_columns() -> None:
    """data/contracts.md fixes the schema of monthly_event_phase_summary.csv."""
    frame = pd.DataFrame(
        {
            "product": ["diesel", "diesel", "gasoline", "gasoline"],
            "event_phase": ["pre_matosinhos_closure", "post_stress"] * 2,
            "imports_kt": [10.0, 14.0, 20.0, 22.0],
        }
    )

    out = monthly_phase_summary(frame, value_column="imports_kt")

    assert list(out.columns) == [
        "product",
        "event_phase",
        "n_months",
        "mean_value",
        "std_value",
    ]


def _planted_monthly_frame(
    *, level_shift: float = 0.0, slope_change: float = 0.0, base_slope: float = 0.5
) -> tuple[pd.DataFrame, int]:
    """Build a noiseless monthly series with a known break at the May 2021 boundary."""
    dates = pd.date_range("2019-01-01", periods=72, freq="MS")
    phase = assign_monthly_event_phase(pd.Series(dates))
    trend = np.arange(len(dates), dtype=float)
    post = (phase != "pre_matosinhos_closure").to_numpy()
    boundary = int(np.flatnonzero(post)[0])
    frame = pd.DataFrame(
        {
            "date": dates,
            "month": dates.month,
            "event_phase": phase,
            "imports_kt": (
                100.0
                + base_slope * trend
                + level_shift * post
                + slope_change * np.maximum(trend - boundary, 0.0)
            ),
        }
    )
    return frame, boundary


def test_fit_monthly_event_model_includes_phase_terms() -> None:
    dates = pd.date_range("2019-01-01", periods=60, freq="MS")
    trend = np.arange(len(dates), dtype=float)
    frame = pd.DataFrame(
        {
            "date": dates,
            "month": dates.month,
            "event_phase": assign_monthly_event_phase(pd.Series(dates)),
            "imports_kt": 100.0 + trend + np.sin(trend),
        }
    )

    result = fit_monthly_event_model(frame, value_column="imports_kt")

    assert "matosinhos_transition" in result.params.index
    assert "energy_stress_2022" in result.params.index
    assert "post_stress" in result.params.index


def test_phase_coefficient_is_the_level_shift_at_the_phase_boundary() -> None:
    """The phase term must be the jump at the boundary, not an intercept at trend 0.

    The interaction is what makes this non-trivial: with an uncentred phase-trend
    term the coefficient is displaced by ``slope_change * boundary``, which here
    would flip a planted +20 shift to -8.
    """
    frame, _ = _planted_monthly_frame(level_shift=20.0, slope_change=1.0)

    result = fit_monthly_event_model(frame, value_column="imports_kt")

    assert result.params["matosinhos_transition"] == pytest.approx(20.0)
    assert result.params["matosinhos_transition_trend"] == pytest.approx(1.0)


def test_phase_coefficient_recovers_pure_level_shift() -> None:
    frame, _ = _planted_monthly_frame(level_shift=20.0)

    result = fit_monthly_event_model(frame, value_column="imports_kt")

    assert result.params["matosinhos_transition"] == pytest.approx(20.0)
    assert result.params["matosinhos_transition_trend"] == pytest.approx(0.0, abs=1e-8)


def test_trend_is_measured_in_months_not_observations() -> None:
    """Missing months must not rescale the trend coefficient.

    The gap sits wholly inside the pre-closure phase, which is what identifies the
    base trend. Indexing by row position there would stretch 28 calendar months over
    16 observations and inflate the estimated per-month slope.
    """
    frame, boundary = _planted_monthly_frame(base_slope=0.5)
    gappy = frame.drop(frame.index[8:20]).reset_index(drop=True)
    assert (gappy["event_phase"] == "pre_matosinhos_closure").sum() == boundary - 12

    complete = fit_monthly_event_model(frame, value_column="imports_kt")
    with_gap = fit_monthly_event_model(gappy, value_column="imports_kt")

    assert complete.params["trend"] == pytest.approx(0.5)
    assert with_gap.params["trend"] == pytest.approx(0.5)


def _phased_panel(slope: float = 0.05) -> pd.DataFrame:
    """A monthly series that opens a phase at the counterfactual and drifts up within it."""
    dates = pd.date_range("2015-01-01", "2024-12-01", freq="MS")
    frame = pd.DataFrame({"date": dates})
    frame["month"] = frame["date"].dt.month
    frame["event_phase"] = assign_monthly_event_phase(frame["date"])
    elapsed = np.arange(len(frame), dtype=float)
    within = frame["event_phase"].eq("matosinhos_transition")
    months_in = np.where(within, elapsed - elapsed[within.to_numpy()].min(), 0.0)
    frame["value"] = 10.0 + 0.01 * elapsed + slope * months_in
    return frame


def test_phase_contrasts_report_the_path_not_only_its_first_month() -> None:
    """The level term is the contrast where the phase opens, which is not where it ends.

    The diesel ratio opens the transition at 0.088 with p=0.307 and closes it at 0.402 with
    p=0.002, so quoting the level term alone describes only the first of those.
    """
    panel = _phased_panel()
    model = fit_monthly_event_model(panel, value_column="value")
    out = phase_contrasts(model, panel, value_column="value")

    transition = out[out["phase"] == "matosinhos_transition"].set_index("at")
    assert transition.loc["first month", "months_into_phase"] == 0.0
    assert transition.loc["last month", "months_into_phase"] > 0.0
    # the series drifts upward inside the phase, so the contrast must grow across it
    assert transition.loc["last month", "contrast"] > transition.loc["first month", "contrast"]
    assert (transition["ci_low"] < transition["contrast"]).all()
    assert (transition["contrast"] < transition["ci_high"]).all()


def test_phase_contrasts_label_the_specification() -> None:
    panel = _phased_panel()
    without = phase_contrasts(
        fit_monthly_event_model(panel, value_column="value"), panel, value_column="value"
    )
    assert set(without["specification"]) == {"no 2013 control"}
