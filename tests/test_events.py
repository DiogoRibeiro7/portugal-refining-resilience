import numpy as np
import pandas as pd

from portugal_refining_resilience.events import (
    annual_event_role,
    assign_monthly_event_phase,
    fit_monthly_event_model,
    monthly_phase_summary,
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
