from __future__ import annotations

import pandas as pd
import statsmodels.api as sm


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


def monthly_phase_summary(
    df: pd.DataFrame,
    *,
    value_column: str,
    group_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Summarise monthly outcomes by event phase."""
    group_columns = group_columns or ["product", "event_phase"]
    required = set(group_columns) | {value_column}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Monthly phase summary missing columns: {sorted(missing)}")
    values = pd.to_numeric(df[value_column], errors="coerce")
    frame = df.loc[values.notna()].copy()
    frame[value_column] = values.loc[values.notna()]
    return (
        frame.groupby(group_columns, as_index=False)[value_column]
        .agg(["count", "mean", "std"])
        .reset_index()
        .rename(
            columns={
                "count": "n_months",
                "mean": "mean_value",
                "std": "std_value",
            }
        )
    )


def fit_monthly_event_model(
    df: pd.DataFrame,
    *,
    value_column: str,
    min_observations: int = 24,
) -> object:
    """Fit a segmented monthly event model with month fixed effects and HAC errors."""
    required = {"date", "month", "event_phase", value_column}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Monthly event model missing columns: {sorted(missing)}")
    frame = df[["date", "month", "event_phase", value_column]].dropna().copy()
    if len(frame) < min_observations:
        raise ValueError(f"Need at least {min_observations} monthly observations")
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    frame["trend"] = range(len(frame))
    frame["matosinhos_transition"] = frame["event_phase"].eq("matosinhos_transition").astype(int)
    frame["energy_stress_2022"] = frame["event_phase"].eq("energy_stress_2022").astype(int)
    frame["post_stress"] = frame["event_phase"].eq("post_stress").astype(int)
    for phase in ["matosinhos_transition", "energy_stress_2022", "post_stress"]:
        frame[f"{phase}_trend"] = frame[phase] * frame["trend"]
    month_dummies = pd.get_dummies(frame["month"].astype(int), prefix="month", drop_first=True)
    x = pd.concat(
        [
            frame[
                [
                    "trend",
                    "matosinhos_transition",
                    "matosinhos_transition_trend",
                    "energy_stress_2022",
                    "energy_stress_2022_trend",
                    "post_stress",
                    "post_stress_trend",
                ]
            ],
            month_dummies,
        ],
        axis=1,
    ).astype(float)
    x = sm.add_constant(x, has_constant="add")
    return sm.OLS(frame[value_column].astype(float), x).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
