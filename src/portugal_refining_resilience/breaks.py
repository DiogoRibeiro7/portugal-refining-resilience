from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import f
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.stattools import durbin_watson


@dataclass(frozen=True)
class ChowResult:
    """Result of a known-break Chow test."""

    break_year: int
    f_statistic: float
    p_value: float
    n_pre: int
    n_post: int
    excluded_years: tuple[int, ...] = ()


def _rss(y: np.ndarray, x: np.ndarray) -> tuple[float, int]:
    model = sm.OLS(y, sm.add_constant(x, has_constant="add")).fit()
    residuals = np.asarray(model.resid, dtype=float)
    return float(residuals @ residuals), int(model.df_model) + 1


def _drop_transition_years(
    frame: pd.DataFrame, transition_years: tuple[int, ...] = ()
) -> pd.DataFrame:
    if not transition_years:
        return frame
    return frame.loc[~frame["year"].isin(transition_years)].copy()


def chow_test(
    year: pd.Series,
    value: pd.Series,
    *,
    break_year: int,
    transition_years: tuple[int, ...] = (),
) -> ChowResult:
    """Perform a transparent Chow test for a pre-specified annual break year.

    The model on each side is a linear trend. This is a diagnostic, not a causal estimator.
    Transition years are excluded before splitting the pre/post samples.
    """
    frame = _drop_transition_years(
        pd.DataFrame({"year": year, "value": value}).dropna().sort_values("year"),
        transition_years,
    )
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
    return ChowResult(break_year, float(f_stat), p_value, len(pre), len(post), transition_years)


def interrupted_time_series(
    df: pd.DataFrame,
    *,
    value_column: str,
    event_year: int,
    transition_years: tuple[int, ...] = (),
    control_events: tuple[int, ...] = (),
    cov_type: str = "HAC",
    maxlags: int = 1,
) -> object:
    """Fit level and slope changes around an event using robust covariance.

    ``control_events`` adds a level and slope term for each earlier documented break.
    Without them a single trend is fitted through the whole panel, and where an earlier
    event moved the series the counterfactual the event of interest is measured against
    is drawn through that movement. For Portuguese diesel exports the 2013 hydrocracker
    is the largest feature of the series, so a 2022 model that ignores it is comparing
    2022 with a trend the 2013 unit helped set.
    """
    frame = _drop_transition_years(
        df[["year", value_column]].dropna().sort_values("year").copy(),
        transition_years,
    )
    frame["trend"] = frame["year"] - int(frame["year"].min())
    frame["post"] = (frame["year"] >= event_year).astype(int)
    frame["post_trend"] = (frame["year"] - event_year).clip(lower=0)
    columns = ["trend", "post", "post_trend"]
    for control in sorted(set(control_events) - {event_year}):
        frame[f"post_{control}"] = (frame["year"] >= control).astype(int)
        frame[f"post_trend_{control}"] = (frame["year"] - control).clip(lower=0)
        columns += [f"post_{control}", f"post_trend_{control}"]
    x = sm.add_constant(frame[columns], has_constant="add")
    cov_kwds = {"maxlags": maxlags} if cov_type.upper() == "HAC" else None
    return sm.OLS(frame[value_column].astype(float), x).fit(cov_type=cov_type, cov_kwds=cov_kwds)


@dataclass(frozen=True)
class SupWaldResult:
    """Outcome of a search over break dates rather than a test at one chosen date."""

    statistic: float
    break_year: int
    p_value: float
    n_candidates: int
    n_simulations: int
    null_95th_percentile: float


def andrews_sup_wald(
    df: pd.DataFrame,
    *,
    value_column: str,
    trim: float = 0.15,
    n_simulations: int = 400,
    seed: int = 20260821,
) -> SupWaldResult:
    """Test for a break at an unknown date, for breaks that were chosen by looking.

    A Chow test is valid when the break year was specified before seeing the series. A
    year picked because the series appeared to move there has been selected as the
    maximum of many tests, and its F must be judged against the distribution of that
    maximum rather than against the distribution of a single test. Ignoring the
    difference makes an exploratory break look pre-specified.

    The null distribution is simulated by refitting a no-break trend, resampling
    Gaussian errors at its residual scale, and repeating the search, so the reported
    p-value needs no critical-value table and no asymptotic approximation.
    """
    frame = df[["year", value_column]].dropna().sort_values("year")
    years = frame["year"].to_numpy(dtype=float)
    values = frame[value_column].to_numpy(dtype=float)
    if len(years) < 12:
        raise ValueError("Need at least 12 observations to search for a break date")

    trend = years - years.min()
    lower = int(np.floor(len(years) * trim))
    upper = int(np.ceil(len(years) * (1.0 - trim)))
    candidates = years[lower:upper]
    if len(candidates) < 2:
        raise ValueError("Trimming left fewer than two candidate break years")

    restriction = np.array([[0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]])

    def search(target: np.ndarray) -> tuple[float, int]:
        best, best_year = -np.inf, int(candidates[0])
        for candidate in candidates:
            post = (years >= candidate).astype(float)
            post_trend = np.clip(years - candidate, 0.0, None)
            design = np.column_stack([np.ones(len(years)), trend, post, post_trend])
            statistic = float(sm.OLS(target, design).fit().f_test(restriction).fvalue)
            if statistic > best:
                best, best_year = statistic, int(candidate)
        return best, best_year

    observed, break_year = search(values)

    null_design = np.column_stack([np.ones(len(years)), trend])
    null_fit = sm.OLS(values, null_design).fit()
    scale = float(np.sqrt(null_fit.mse_resid))
    rng = np.random.default_rng(seed)
    simulated = np.array(
        [
            search(np.asarray(null_fit.fittedvalues) + rng.normal(0.0, scale, len(years)))[0]
            for _ in range(n_simulations)
        ]
    )
    return SupWaldResult(
        statistic=observed,
        break_year=break_year,
        p_value=float(np.mean(simulated >= observed)),
        n_candidates=int(len(candidates)),
        n_simulations=int(n_simulations),
        null_95th_percentile=float(np.percentile(simulated, 95)),
    )


def residual_diagnostics(model: object, *, label: str = "") -> dict[str, float | int | str]:
    """Summarise how well a fitted model describes its series, and whether it is misspecified.

    Coefficient tables say which terms are distinguishable from zero. They do not say
    whether the model accounts for any of the variation, nor whether what it leaves
    behind is still autocorrelated, which for an annual or monthly series is the
    failure that invalidates the standard errors reported beside them.
    """
    fitted = cast(Any, model)
    residuals = np.asarray(fitted.resid, dtype=float)
    record: dict[str, float | int | str] = {
        "model": label,
        "n_obs": int(fitted.nobs),
        "r_squared": float(fitted.rsquared),
        "adj_r_squared": float(fitted.rsquared_adj),
        "residual_sd": float(np.std(residuals, ddof=1)),
        "durbin_watson": float(durbin_watson(residuals)),
    }
    lags = min(4, max(1, len(residuals) // 5))
    try:
        ljung = acorr_ljungbox(residuals, lags=[lags], return_df=True)
        ljung_p = float(ljung["lb_pvalue"].iloc[0])
        record["ljung_box_lag"] = int(lags)
        record["ljung_box_p_value"] = ljung_p
        record["residual_autocorrelation_5pct"] = bool(ljung_p < 0.05)
    except (ValueError, IndexError):
        record["ljung_box_lag"] = int(lags)
        record["ljung_box_p_value"] = float("nan")
        record["residual_autocorrelation_5pct"] = False
    return record


def coefficient_table(model: object, *, alpha: float = 0.05, **context: object) -> pd.DataFrame:
    """Return coefficients with confidence intervals rather than estimates and stars.

    An interval says how precise an estimate is on the scale the estimate is measured
    in. A p-value says only whether zero is excluded, which for a level shift measured
    in kilotonnes is the least interesting thing about it.
    """
    fitted = cast(Any, model)
    intervals = fitted.conf_int(alpha=alpha)
    rows: list[dict[str, object]] = []
    for term in fitted.params.index:
        rows.append(
            {
                **context,
                "term": str(term),
                "estimate": float(fitted.params[term]),
                "std_error": float(fitted.bse[term]),
                "p_value": float(fitted.pvalues[term]),
                "ci_low": float(intervals.loc[term].iloc[0]),
                "ci_high": float(intervals.loc[term].iloc[1]),
                "ci_level": 1.0 - alpha,
                "nobs": int(fitted.nobs),
            }
        )
    return pd.DataFrame(rows)


def global_break_search(
    df: pd.DataFrame,
    *,
    value_column: str,
    max_breaks: int = 3,
    min_segment: int = 5,
) -> pd.DataFrame:
    """Locate multiple breaks jointly instead of testing candidate dates one at a time.

    Testing candidates separately asks whether a particular year is a break given that no
    other break exists, which is false whenever the series has more than one. Minimising
    the residual sum of squares over every admissible combination and selecting the number
    of breaks by BIC asks the question the panel actually poses, and it can decline to
    place a break where a single-date test found one.

    ``min_segment`` trims the ends and the interval between breaks. Any year inside the
    trimmed region cannot be selected however strong the evidence for it, so a date near
    the end of a short panel is outside what this search can see.
    """
    required = {"year", value_column}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Break search missing columns: {sorted(missing)}")

    frame = df[["year", value_column]].dropna().sort_values("year")
    years = frame["year"].to_numpy(dtype=float)
    values = frame[value_column].to_numpy(dtype=float)
    n = len(years)
    if n < 4 * min_segment:
        raise ValueError(f"Need at least {4 * min_segment} observations for this search")

    candidates = [int(year) for year in years[min_segment : n - min_segment]]

    def fit(breaks: tuple[int, ...]) -> tuple[float, int]:
        columns = [np.ones(n), years - years.min()]
        for cut in breaks:
            columns.append((years >= cut).astype(float))
            columns.append(np.clip(years - cut, 0.0, None))
        matrix = np.column_stack(columns)
        return float(sm.OLS(values, matrix).fit().ssr), int(matrix.shape[1])

    rows: list[dict[str, object]] = []
    for count in range(max_breaks + 1):
        best_bic: float = float("inf")
        best_set: tuple[int, ...] = ()
        best_ssr: float = float("nan")
        for combo in itertools.combinations(candidates, count):
            if any(
                later - earlier < min_segment
                for earlier, later in zip(combo, combo[1:], strict=False)
            ):
                continue
            residual, parameters = fit(combo)
            bic = n * np.log(residual / n) + parameters * np.log(n)
            if bic < best_bic:
                best_bic, best_set, best_ssr = bic, combo, residual
        rows.append(
            {
                "outcome": value_column,
                "n_breaks": count,
                "break_years": ",".join(str(int(year)) for year in best_set),
                "ssr": best_ssr,
                "bic": best_bic,
                "n_obs": n,
                "min_segment": min_segment,
                "earliest_candidate": candidates[0],
                "latest_candidate": candidates[-1],
            }
        )
    table = pd.DataFrame(rows)
    table["selected_by_bic"] = table["bic"] == table["bic"].min()
    return table
