from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint


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


def spread_stationarity(design: pd.DataFrame) -> dict[str, float | int | str | bool]:
    """Run ADF on the PT-ES spread."""
    required = {"PT", "ES"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")
    spread = pd.to_numeric(design["PT"] - design["ES"], errors="coerce").dropna()
    if len(spread) < 20 or spread.nunique() < 2:
        return {
            "diagnostic": "pt_es_spread_adf",
            "status": "insufficient_observations",
            "nobs": int(len(spread)),
            "p_value": float("nan"),
            "stationary_5pct": False,
        }
    adf_statistic, p_value, used_lag, nobs, *_ = adfuller(spread, autolag="AIC")
    return {
        "diagnostic": "pt_es_spread_adf",
        "status": "estimated",
        "nobs": int(len(spread)),
        "adf_statistic": float(adf_statistic),
        "p_value": float(p_value),
        "used_lag": int(used_lag),
        "adf_nobs": int(nobs),
        "stationary_5pct": bool(p_value < 0.05),
    }


def choose_price_model(design: pd.DataFrame, *, product: str) -> dict[str, object]:
    """Choose a price model family from stationarity and cointegration diagnostics."""
    required = {"PT", "ES"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")
    paired = design[["PT", "ES"]].apply(pd.to_numeric, errors="coerce").dropna()
    pt = paired["PT"]
    es = paired["ES"]
    if len(paired) < 20 or pt.nunique() < 2 or es.nunique() < 2:
        return {
            "product": product,
            "model_family": "insufficient_observations",
            "reason": "Need at least 20 non-constant paired observations",
            "n_obs": int(len(paired)),
        }

    pt_level_p = float(adfuller(pt, autolag="AIC")[1])
    es_level_p = float(adfuller(es, autolag="AIC")[1])
    if pt_level_p < 0.05 and es_level_p < 0.05:
        return {
            "product": product,
            "model_family": "levels",
            "reason": "PT and ES levels reject unit-root null at 5%",
            "n_obs": int(len(paired)),
            "pt_level_adf_p_value": pt_level_p,
            "es_level_adf_p_value": es_level_p,
        }

    coint_stat, coint_p, _ = coint(pt, es)
    if float(coint_p) < 0.05:
        return {
            "product": product,
            "model_family": "ecm_required",
            "reason": "Levels appear nonstationary but PT and ES are cointegrated",
            "n_obs": int(len(paired)),
            "pt_level_adf_p_value": pt_level_p,
            "es_level_adf_p_value": es_level_p,
            "cointegration_statistic": float(coint_stat),
            "cointegration_p_value": float(coint_p),
        }
    return {
        "product": product,
        "model_family": "short_run_log_difference",
        "reason": "Levels do not both reject unit-root null and cointegration is not detected",
        "n_obs": int(len(paired)),
        "pt_level_adf_p_value": pt_level_p,
        "es_level_adf_p_value": es_level_p,
        "cointegration_statistic": float(coint_stat),
        "cointegration_p_value": float(coint_p),
    }


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


def fit_short_run_price_transmission(design: pd.DataFrame) -> object:
    """Fit short-run PT-ES log-difference transmission with post interaction."""
    required = {"diff_log_PT", "diff_log_ES", "post"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")
    frame = design.dropna(subset=["diff_log_PT", "diff_log_ES", "post"]).copy()
    frame["diff_log_ES_x_post"] = frame["diff_log_ES"] * frame["post"]
    x = sm.add_constant(frame[["diff_log_ES", "diff_log_ES_x_post", "post"]], has_constant="add")
    return sm.OLS(frame["diff_log_PT"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
