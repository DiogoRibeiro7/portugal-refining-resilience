from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import f
import statsmodels.api as sm


@dataclass(frozen=True)
class ChowResult:
    """Result of a known-break Chow test."""

    break_year: int
    f_statistic: float
    p_value: float
    n_pre: int
    n_post: int


def _rss(y: np.ndarray, x: np.ndarray) -> tuple[float, int]:
    model = sm.OLS(y, sm.add_constant(x, has_constant="add")).fit()
    residuals = np.asarray(model.resid, dtype=float)
    return float(residuals @ residuals), int(model.df_model) + 1


def chow_test(year: pd.Series, value: pd.Series, *, break_year: int) -> ChowResult:
    """Perform a transparent Chow test for a pre-specified annual break year.

    The model on each side is a linear trend. This is a diagnostic, not a causal estimator.
    """
    frame = pd.DataFrame({"year": year, "value": value}).dropna().sort_values("year")
    pre = frame.loc[frame["year"] < break_year]
    post = frame.loc[frame["year"] >= break_year]
    if len(pre) < 3 or len(post) < 3:
        raise ValueError("Need at least three observations on each side of the break")

    x_full = frame[["year"]].to_numpy(dtype=float)
    y_full = frame["value"].to_numpy(dtype=float)
    rss_pooled, k = _rss(y_full, x_full)
    rss_pre, _ = _rss(pre["value"].to_numpy(dtype=float), pre[["year"]].to_numpy(dtype=float))
    rss_post, _ = _rss(post["value"].to_numpy(dtype=float), post[["year"]].to_numpy(dtype=float))

    n = len(frame)
    numerator = max((rss_pooled - rss_pre - rss_post) / k, 0.0)
    denominator = (rss_pre + rss_post) / (n - 2 * k)
    f_stat = numerator / denominator if denominator > 0 else float("inf")
    p_value = float(f.sf(f_stat, k, n - 2 * k))
    return ChowResult(break_year, float(f_stat), p_value, len(pre), len(post))


def interrupted_time_series(
    df: pd.DataFrame,
    *,
    value_column: str,
    event_year: int,
) -> object:
    """Fit level and slope changes around an event using OLS with HC1 covariance."""
    frame = df[["year", value_column]].dropna().sort_values("year").copy()
    frame["trend"] = frame["year"] - int(frame["year"].min())
    frame["post"] = (frame["year"] >= event_year).astype(int)
    frame["post_trend"] = (frame["year"] - event_year).clip(lower=0)
    x = sm.add_constant(frame[["trend", "post", "post_trend"]], has_constant="add")
    return sm.OLS(frame[value_column].astype(float), x).fit(cov_type="HC1")
