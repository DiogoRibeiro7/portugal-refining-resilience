from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller


def price_comovement_design(
    prices: pd.DataFrame,
    *,
    product: str,
    cutoff: str | pd.Timestamp = "2021-05-01",
    value_column: str = "price_without_tax_eur_per_1000l",
) -> pd.DataFrame:
    """Build a PT-ES weekly price co-movement design matrix."""
    required = {"date", "country", "product", value_column}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"Price frame missing columns: {sorted(missing)}")
    frame = prices.loc[prices["product"] == product].copy()
    frame["date"] = pd.to_datetime(frame["date"])
    wide = (
        frame.pivot(index="date", columns="country", values=value_column)
        .dropna(subset=["PT", "ES"])
        .reset_index()
        .sort_values("date")
    )
    transition_date = pd.Timestamp(cutoff)
    wide["trend"] = np.arange(len(wide), dtype=float)
    wide["post"] = (wide["date"] >= transition_date).astype(int)
    wide["ES_x_post"] = wide["ES"] * wide["post"]
    post_origin = np.searchsorted(wide["date"].to_numpy(), np.datetime64(transition_date))
    wide["post_trend"] = np.maximum(wide["trend"].to_numpy(dtype=float) - float(post_origin), 0.0)
    wide["log_PT"] = np.log(wide["PT"])
    wide["log_ES"] = np.log(wide["ES"])
    wide["diff_log_PT"] = wide["log_PT"].diff()
    wide["diff_log_ES"] = wide["log_ES"].diff()
    return wide


def stationarity_diagnostics(
    df: pd.DataFrame,
    *,
    value_column: str,
    group_columns: list[str],
    min_observations: int = 20,
) -> pd.DataFrame:
    """Run ADF diagnostics by group for persistent price-level guardrails."""
    required = set(group_columns) | {value_column}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Stationarity frame missing columns: {sorted(missing)}")
    records: list[dict[str, float | int | str | bool]] = []
    grouper = group_columns[0] if len(group_columns) == 1 else group_columns
    for keys, group in df.groupby(grouper):
        values = pd.to_numeric(group[value_column], errors="coerce").dropna()
        key_values = keys if isinstance(keys, tuple) else (keys,)
        record: dict[str, float | int | str | bool] = {
            column: str(value) for column, value in zip(group_columns, key_values, strict=True)
        }
        record["value_column"] = value_column
        record["nobs"] = int(len(values))
        if len(values) < min_observations or values.nunique() < 2:
            record["status"] = "insufficient_observations"
            record["adf_statistic"] = np.nan
            record["p_value"] = np.nan
            record["stationary_5pct"] = False
        else:
            adf_statistic, p_value, used_lag, nobs, *_ = adfuller(values, autolag="AIC")
            record["status"] = "estimated"
            record["adf_statistic"] = float(adf_statistic)
            record["p_value"] = float(p_value)
            record["used_lag"] = int(used_lag)
            record["adf_nobs"] = int(nobs)
            record["stationary_5pct"] = bool(p_value < 0.05)
        records.append(record)
    return pd.DataFrame(records)


def fit_price_comovement(design: pd.DataFrame) -> object:
    """Fit PT-ES price co-movement with HAC covariance."""
    required = {"PT", "ES", "ES_x_post", "trend", "post", "post_trend"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")
    x = sm.add_constant(
        design[["ES", "ES_x_post", "trend", "post", "post_trend"]], has_constant="add"
    )
    return sm.OLS(design["PT"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
