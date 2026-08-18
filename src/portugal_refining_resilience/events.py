from __future__ import annotations

import pandas as pd


def assign_monthly_event_phase(
    dates: pd.Series,
    *,
    closure_date: str | pd.Timestamp = "2021-05-01",
    energy_stress_date: str | pd.Timestamp = "2022-03-01",
    post_stress_date: str | pd.Timestamp = "2023-01-01",
) -> pd.Series:
    """Classify monthly observations into event-timing phases."""
    parsed = pd.to_datetime(dates)
    closure = pd.Timestamp(closure_date)
    stress = pd.Timestamp(energy_stress_date)
    post_stress = pd.Timestamp(post_stress_date)
    if not closure < stress < post_stress:
        raise ValueError("Expected closure_date < energy_stress_date < post_stress_date")

    phase = pd.Series("pre_matosinhos_closure", index=dates.index, dtype="object")
    phase.loc[(parsed >= closure) & (parsed < stress)] = "matosinhos_transition"
    phase.loc[(parsed >= stress) & (parsed < post_stress)] = "energy_stress_2022"
    phase.loc[parsed >= post_stress] = "post_stress"
    return phase


def annual_event_role(years: pd.Series, *, transition_year: int = 2021) -> pd.Series:
    """Classify annual observations without assigning the transition year to pre/post."""
    numeric = pd.to_numeric(years, errors="coerce")
    role = pd.Series("pre_transition", index=years.index, dtype="object")
    role.loc[numeric == transition_year] = "transition"
    role.loc[numeric > transition_year] = "post_transition"
    role.loc[numeric.isna()] = None
    return role
