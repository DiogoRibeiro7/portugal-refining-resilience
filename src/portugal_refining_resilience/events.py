from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd
import statsmodels.api as sm

EVENT_PHASES: tuple[str, ...] = (
    "matosinhos_transition",
    "energy_stress_2022",
    "post_stress",
)


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

    # Every comparison against NaT is False, so a missing date would keep the default
    # and be silently reported as a pre-closure observation. An undated row belongs to
    # no phase, and saying so lets the panel validation see it.
    phase = pd.Series("pre_matosinhos_closure", index=dates.index, dtype="object")
    phase.loc[(parsed >= closure) & (parsed < stress)] = "matosinhos_transition"
    phase.loc[(parsed >= stress) & (parsed < post_stress)] = "energy_stress_2022"
    phase.loc[parsed >= post_stress] = "post_stress"
    phase.loc[parsed.isna()] = None
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
    return frame.groupby(group_columns, as_index=False).agg(
        n_months=(value_column, "count"),
        mean_value=(value_column, "mean"),
        std_value=(value_column, "std"),
    )


def fit_monthly_event_model(
    df: pd.DataFrame,
    *,
    value_column: str,
    min_observations: int = 24,
    control_year: int | None = None,
) -> object:
    """Fit a segmented monthly event model with month fixed effects and HAC errors.

    ``trend`` counts elapsed calendar months from the first observation, so gaps in the
    monthly series do not compress the time axis.

    Each phase-trend interaction is centred on that phase's first observed month. The
    phase indicator is therefore the level shift at the phase boundary, measured against
    the extrapolated pre-closure trend, rather than an intercept at ``trend == 0``. Read
    together with its ``*_trend`` term it gives the level and slope change for the phase.

    ``control_year`` adds a level and slope term at an earlier documented event. The
    monthly panel begins in 2002 and the 2013 hydrocracker raises diesel refinery output
    and exports by a large step inside it, so without such a term the pre-closure trend
    every phase coefficient is measured against is fitted through that step. The annual
    models carry the same control for the same reason, and there it moved a headline
    estimate materially.
    """
    required = {"date", "month", "event_phase", value_column}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Monthly event model missing columns: {sorted(missing)}")
    frame = df[["date", "month", "event_phase", value_column]].dropna().copy()
    if len(frame) < min_observations:
        raise ValueError(f"Need at least {min_observations} monthly observations")
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    elapsed_months = frame["date"].dt.year * 12 + frame["date"].dt.month
    frame["trend"] = (elapsed_months - elapsed_months.min()).astype(float)
    control_columns: list[str] = []
    if control_year is not None:
        indicator = frame["date"].dt.year >= int(control_year)
        name = f"control_{int(control_year)}"
        frame[name] = indicator.astype(int)
        boundary = float(frame.loc[indicator, "trend"].min()) if indicator.any() else 0.0
        frame[f"{name}_trend"] = frame[name] * (frame["trend"] - boundary)
        control_columns = [name, f"{name}_trend"]
    for phase in EVENT_PHASES:
        indicator = frame["event_phase"].eq(phase)
        frame[phase] = indicator.astype(int)
        boundary = float(frame.loc[indicator, "trend"].min()) if indicator.any() else 0.0
        frame[f"{phase}_trend"] = frame[phase] * (frame["trend"] - boundary)
    month_dummies = pd.get_dummies(frame["month"].astype(int), prefix="month", drop_first=True)
    design_columns = ["trend", *control_columns]
    for phase in EVENT_PHASES:
        design_columns.extend([phase, f"{phase}_trend"])
    x = pd.concat([frame[design_columns], month_dummies], axis=1).astype(float)
    x = sm.add_constant(x, has_constant="add")
    return sm.OLS(frame[value_column].astype(float), x).fit(cov_type="HAC", cov_kwds={"maxlags": 3})


def phase_contrasts(
    model: object,
    df: pd.DataFrame,
    *,
    value_column: str,
    control_year: int | None = None,
) -> pd.DataFrame:
    """Fitted distance from the pre-closure counterfactual, at each phase boundary and end.

    The phase indicator is the level shift where the phase begins and the ``*_trend`` term is
    the slope within it, both measured against the extrapolated pre-closure trend. Quoting the
    indicator alone therefore describes the path only at its first month. For the diesel
    net-import ratio with 2013 held constant the level term is $0.088$ ($p=0.307$) while the
    slope is $0.035$ a month ($p=0.024$): the phase begins indistinguishable from the
    counterfactual and ends well above it, and the level term alone says the first thing and
    not the second.

    Each row is the linear combination

    contrast at t = phase level shift + phase slope * (t - phase start),

    tested with the same HAC covariance as the model, so the interval is directly comparable
    with the coefficients.
    """
    fitted = cast(Any, model)
    names = list(fitted.model.exog_names)

    frame = df[["date", "month", "event_phase", value_column]].dropna().copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    elapsed = frame["date"].dt.year * 12 + frame["date"].dt.month
    frame["trend"] = (elapsed - elapsed.min()).astype(float)

    rows: list[dict[str, object]] = []
    for phase in EVENT_PHASES:
        block = frame.loc[frame["event_phase"].eq(phase)]
        if block.empty or phase not in names or f"{phase}_trend" not in names:
            continue
        boundary = float(block["trend"].min())
        for label, moment in (
            ("first month", block["trend"].min()),
            ("last month", block["trend"].max()),
        ):
            restriction = np.zeros(len(names))
            restriction[names.index(phase)] = 1.0
            restriction[names.index(f"{phase}_trend")] = float(moment) - boundary
            test = fitted.t_test(restriction)
            interval = np.asarray(test.conf_int()).ravel()
            rows.append(
                {
                    "outcome": value_column,
                    "phase": phase,
                    "at": label,
                    "date": str(
                        block["date"].min().date()
                        if label == "first month"
                        else block["date"].max().date()
                    ),
                    "months_into_phase": float(moment) - boundary,
                    "contrast": float(np.ravel(test.effect)[0]),
                    "std_error": float(np.ravel(test.sd)[0]),
                    "p_value": float(np.ravel(test.pvalue)[0]),
                    "ci_low": float(interval[0]),
                    "ci_high": float(interval[1]),
                    "specification": "2013 held constant" if control_year else "no 2013 control",
                }
            )
    return pd.DataFrame(rows)


def phase_joint_tests(
    model: object,
    *,
    value_column: str,
    control_year: int | None = None,
) -> pd.DataFrame:
    """Test each phase as one hypothesis, and all phases together.

    A phase enters through a level term and a slope term, and reading significance off
    whichever is smaller is the same multiplicity the price family has. The joint restriction
    that both are zero asks whether the phase differs from the counterfactual at all, which is
    what the prose claims. The final row tests every phase at once, so a reader can see whether
    the segmented structure earns its degrees of freedom.
    """
    fitted = cast(Any, model)
    names = set(fitted.model.exog_names)

    rows: list[dict[str, object]] = []
    present: list[str] = []
    for phase in EVENT_PHASES:
        terms = [phase, f"{phase}_trend"]
        if not set(terms) <= names:
            continue
        present.extend(terms)
        test = fitted.f_test(", ".join(f"{term} = 0" for term in terms))
        rows.append(
            {
                "outcome": value_column,
                "hypothesis": phase,
                "terms": len(terms),
                "f_statistic": float(np.ravel(test.fvalue)[0]),
                "df_num": int(test.df_num),
                "df_denom": int(test.df_denom),
                "p_value": float(test.pvalue),
                "rejected_5pct": bool(float(test.pvalue) < 0.05),
                "specification": "2013 held constant" if control_year else "no 2013 control",
            }
        )

    if present:
        test = fitted.f_test(", ".join(f"{term} = 0" for term in present))
        rows.append(
            {
                "outcome": value_column,
                "hypothesis": "all phases",
                "terms": len(present),
                "f_statistic": float(np.ravel(test.fvalue)[0]),
                "df_num": int(test.df_num),
                "df_denom": int(test.df_denom),
                "p_value": float(test.pvalue),
                "rejected_5pct": bool(float(test.pvalue) < 0.05),
                "specification": "2013 held constant" if control_year else "no 2013 control",
            }
        )
    return pd.DataFrame(rows)
