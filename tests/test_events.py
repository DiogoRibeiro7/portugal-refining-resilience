import pandas as pd

from portugal_refining_resilience.events import annual_event_role, assign_monthly_event_phase


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
