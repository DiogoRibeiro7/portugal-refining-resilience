from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint, kpss
from statsmodels.tsa.vector_ar.vecm import coint_johansen

#: Weekly Oil Bulletin product tokens mapped to this project's canonical products.
_BULLETIN_PRODUCTS: dict[str, str] = {"euro95": "gasoline", "diesel": "diesel"}

#: The bulletin quotes road fuels per 1000 litres. Anything else must not be
#: silently rebadged as a EUR/1000L price.
_BULLETIN_UNIT = "1000 l"

_BULLETIN_HEADER = re.compile(
    r"^(?P<country>[A-Z]{2,3})_price_(?P<basis>wo|with)_tax_(?P<product>euro95|diesel)$"
)

_BULLETIN_SHEETS: dict[str, str] = {
    "wo": "Prices wo taxes",
    "with": "Prices with taxes",
}


def _extract_bulletin_sheet(
    path: Path,
    sheet: str,
    basis: str,
    countries: tuple[str, ...],
    value_column: str,
) -> pd.DataFrame:
    """Melt one Weekly Oil Bulletin price sheet into long rows."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    if len(raw) < 4:
        raise ValueError(f"Sheet {sheet!r} has too few rows to contain a price history")
    headers = [str(value).strip() for value in raw.iloc[0]]
    units = [str(value).strip().lower() for value in raw.iloc[2]]
    body = raw.iloc[3:].reset_index(drop=True)

    dates = pd.to_datetime(body.iloc[:, 0], errors="coerce")
    records: list[pd.DataFrame] = []
    seen: set[tuple[str, str]] = set()
    for position, header in enumerate(headers):
        match = _BULLETIN_HEADER.match(header)
        if match is None or match.group("basis") != basis:
            continue
        country = match.group("country")
        if country not in countries:
            continue
        if units[position] != _BULLETIN_UNIT:
            raise ValueError(
                f"{sheet!r} column {header!r} is quoted in {units[position]!r}, "
                f"expected {_BULLETIN_UNIT!r}. Re-inventory the workbook before extracting."
            )
        product = _BULLETIN_PRODUCTS[match.group("product")]
        seen.add((country, product))
        records.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "country": country,
                    "product": product,
                    value_column: pd.to_numeric(body.iloc[:, position], errors="coerce"),
                }
            )
        )

    expected = {
        (country, product) for country in countries for product in _BULLETIN_PRODUCTS.values()
    }
    missing = sorted(expected - seen)
    if missing:
        raise ValueError(f"Sheet {sheet!r} is missing price columns for: {missing}")
    return pd.concat(records, ignore_index=True).dropna(subset=["date"])


def extract_weekly_prices(
    path: Path,
    *,
    countries: tuple[str, ...] = ("PT", "ES"),
) -> pd.DataFrame:
    """Extract a tidy weekly price panel from the EC Weekly Oil Bulletin workbook.

    The workbook stores one wide sheet per tax basis, with ``{COUNTRY}_price_{basis}_tax_
    {product}`` header tokens on the first row and units on the third. Layout changes are
    rejected rather than guessed at, because the Commission controls this file and a
    silently mis-parsed column would feed the price models directly.

    Returns the ``weekly_oil_prices_tidy.csv`` contract: ``date``, ``country``,
    ``product``, ``price_with_tax_eur_per_1000l``, ``price_without_tax_eur_per_1000l``.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    without_tax = _extract_bulletin_sheet(
        path, _BULLETIN_SHEETS["wo"], "wo", countries, "price_without_tax_eur_per_1000l"
    )
    with_tax = _extract_bulletin_sheet(
        path, _BULLETIN_SHEETS["with"], "with", countries, "price_with_tax_eur_per_1000l"
    )
    tidy = without_tax.merge(with_tax, on=["date", "country", "product"], how="outer")
    tidy = tidy.dropna(
        subset=["price_without_tax_eur_per_1000l", "price_with_tax_eur_per_1000l"],
        how="all",
    )
    tidy = tidy.sort_values(["country", "product", "date"]).reset_index(drop=True)
    duplicated = tidy.duplicated(["date", "country", "product"], keep=False)
    if duplicated.any():
        examples = tidy.loc[duplicated, ["date", "country", "product"]].head(5).to_dict("records")
        raise ValueError(f"Duplicate weekly price keys: {examples}")
    return tidy[
        [
            "date",
            "country",
            "product",
            "price_with_tax_eur_per_1000l",
            "price_without_tax_eur_per_1000l",
        ]
    ]


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


#: A levels regression is only admissible on strong evidence of stationarity. Getting
#: this branch wrong is the spurious-regression case, whereas an unnecessary
#: error-correction model still nests the difference specification, so the threshold is
#: deliberately stricter than the conventional five per cent.
LEVELS_STATIONARITY_ALPHA = 0.01


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
    """Choose a price model family from stationarity and cointegration diagnostics.

    The diagnostics run on log levels because the models they licence are estimated in
    logs: the short-run specification regresses ``diff_log_PT`` on ``diff_log_ES``, and
    the error-correction model takes its long-run residual from ``log PT`` on
    ``log ES``. Testing the EUR/1000L levels answered a question about a different pair
    of series, and the two disagree where it matters: diesel Engle--Granger is 0.088 on
    levels and 0.022 on logs, which is the difference between fitting an ECM and
    declaring the pair not cointegrated.

    The levels branch requires rejection at ``LEVELS_STATIONARITY_ALPHA`` rather than at
    five per cent. The two mistakes are not symmetric. Regressing one near-integrated
    series on another is the spurious-regression case and its inference is invalid,
    whereas an error-correction model whose series turn out to be stationary still has a
    valid stationary regressor and nests the difference specification. Strong evidence
    is therefore required before the risky branch is taken. The asymmetry is load-bearing
    here: Portuguese and Spanish log gasoline prices fall either side of the five per
    cent line depending on the lag-selection rule alone.
    """
    required = {"log_PT", "log_ES"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")
    paired = design[["log_PT", "log_ES"]].apply(pd.to_numeric, errors="coerce").dropna()
    pt = paired["log_PT"]
    es = paired["log_ES"]
    if len(paired) < 20 or pt.nunique() < 2 or es.nunique() < 2:
        return {
            "product": product,
            "model_family": "insufficient_observations",
            "reason": "Need at least 20 non-constant paired observations",
            "n_obs": int(len(paired)),
            "scale": "log",
        }

    pt_level_p = float(adfuller(pt, autolag="AIC")[1])
    es_level_p = float(adfuller(es, autolag="AIC")[1])
    diagnostics: dict[str, object] = {
        "product": product,
        "n_obs": int(len(paired)),
        "scale": "log",
        "pt_level_adf_p_value": pt_level_p,
        "es_level_adf_p_value": es_level_p,
        "levels_alpha": LEVELS_STATIONARITY_ALPHA,
    }
    if pt_level_p < LEVELS_STATIONARITY_ALPHA and es_level_p < LEVELS_STATIONARITY_ALPHA:
        return {
            **diagnostics,
            "model_family": "levels",
            "reason": (
                "PT and ES log levels both reject the unit-root null at "
                f"{LEVELS_STATIONARITY_ALPHA:.0%}"
            ),
        }

    coint_stat, coint_p, _ = coint(pt, es)
    diagnostics |= {
        "cointegration_statistic": float(coint_stat),
        "cointegration_p_value": float(coint_p),
    }
    if float(coint_p) < 0.05:
        return {
            **diagnostics,
            "model_family": "ecm_required",
            "reason": "Log levels are not clearly stationary and PT and ES are cointegrated",
        }
    return {
        **diagnostics,
        "model_family": "short_run_log_difference",
        "reason": ("Log levels are not clearly stationary and cointegration is not detected"),
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


def fit_error_correction_model(design: pd.DataFrame, *, maxlags: int = 8) -> dict[str, object]:
    """Fit a two-step Engle-Granger ECM for cointegrated PT-ES price levels.

    When ``choose_price_model`` returns ``ecm_required`` the levels are non-stationary
    but move together, so neither a levels regression nor a pure difference model is
    right: the first is spurious, the second discards the long-run relationship.

    Step one estimates the cointegrating regression ``log PT = a + b log ES`` and keeps
    its residual as the disequilibrium term. Step two regresses the weekly change in
    the Portuguese price on the lagged disequilibrium, the contemporaneous Spanish
    change, and interactions of both with the post-transition indicator, so the
    adjustment speed and the short-run pass-through are each allowed to change.

    The error-correction coefficient is expected to be negative: a Portuguese price
    above its long-run relationship with Spain is pulled back down. Its magnitude is
    the share of the gap closed each week.

    The disequilibrium term is a generated regressor, so the second-stage standard
    errors are conditional on the first stage; HAC covariance mitigates but does not
    remove this.
    """
    required = {"log_PT", "log_ES", "diff_log_PT", "diff_log_ES", "post"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")

    levels = design[["log_PT", "log_ES"]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(levels) < 20:
        raise ValueError("Need at least 20 paired price levels to estimate a cointegrating vector")
    long_run = sm.OLS(
        levels["log_PT"], sm.add_constant(levels[["log_ES"]], has_constant="add")
    ).fit()

    frame = design.copy()
    frame["disequilibrium"] = np.nan
    frame.loc[levels.index, "disequilibrium"] = np.asarray(long_run.resid, dtype=float)
    frame["disequilibrium_lag"] = frame["disequilibrium"].shift(1)

    frame = frame.dropna(subset=["diff_log_PT", "diff_log_ES", "disequilibrium_lag", "post"]).copy()
    frame["diff_log_ES_x_post"] = frame["diff_log_ES"] * frame["post"]
    frame["disequilibrium_lag_x_post"] = frame["disequilibrium_lag"] * frame["post"]

    x = sm.add_constant(
        frame[
            [
                "disequilibrium_lag",
                "disequilibrium_lag_x_post",
                "diff_log_ES",
                "diff_log_ES_x_post",
                "post",
            ]
        ],
        has_constant="add",
    )
    model = sm.OLS(frame["diff_log_PT"], x).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return {
        "model": model,
        "cointegrating_constant": float(long_run.params.iloc[0]),
        "cointegrating_slope": float(long_run.params.iloc[1]),
        "n_obs": int(model.nobs),
    }


def adf_lag_rule_sensitivity(design: pd.DataFrame, *, product: str) -> pd.DataFrame:
    """Re-run the log-level unit-root test under each reasonable lag and trend rule.

    The model family turns on whether the log levels are stationary, and for gasoline
    that verdict is marginal. Recording it under one lag rule would present a knife-edge
    result as a settled one, so every rule a reader might reasonably have chosen is
    reported and the paper is held to the least favourable of them.
    """
    required = {"log_PT", "log_ES"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")
    rows: list[dict[str, object]] = []
    for country in ("PT", "ES"):
        series = pd.to_numeric(design[f"log_{country}"], errors="coerce").dropna()
        for regression in ("c", "ct"):
            for rule in ("AIC", "BIC", "fixed_8"):
                if rule == "fixed_8":
                    result = adfuller(series, regression=regression, maxlag=8, autolag=None)
                else:
                    result = adfuller(series, regression=regression, autolag=rule)
                rows.append(
                    {
                        "product": product,
                        "country": country,
                        "regression": regression,
                        "lag_rule": rule,
                        "adf_statistic": float(result[0]),
                        "p_value": float(result[1]),
                        "stationary_5pct": bool(result[1] < 0.05),
                        "stationary_1pct": bool(result[1] < LEVELS_STATIONARITY_ALPHA),
                    }
                )
    return pd.DataFrame(rows)


def model_choice_scale_comparison(design: pd.DataFrame, *, product: str) -> pd.DataFrame:
    """Run the selection diagnostics on both scales and record the disagreement.

    The paper states that the EUR-levels diagnostic and the log diagnostic disagree for
    diesel, and rests a specification decision on it. That comparison has to exist as
    evidence rather than as an assertion about a version of the code that no longer
    runs, so both are computed here and the superseded scale is kept alongside the one
    used.
    """
    required = {"PT", "ES", "log_PT", "log_ES"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")
    rows: list[dict[str, object]] = []
    for scale, columns in (("EUR_per_1000L", ("PT", "ES")), ("log", ("log_PT", "log_ES"))):
        paired = design[list(columns)].apply(pd.to_numeric, errors="coerce").dropna()
        pt, es = paired[columns[0]], paired[columns[1]]
        _, coint_p, _ = coint(pt, es)
        rows.append(
            {
                "product": product,
                "scale": scale,
                "used_for_model_choice": scale == "log",
                "pt_adf_p_value": float(adfuller(pt, autolag="AIC")[1]),
                "es_adf_p_value": float(adfuller(es, autolag="AIC")[1]),
                "cointegration_p_value": float(coint_p),
                "cointegrated_5pct": bool(float(coint_p) < 0.05),
            }
        )
    return pd.DataFrame(rows)


def kpss_levels_diagnostics(design: pd.DataFrame, *, product: str) -> pd.DataFrame:
    """Test the log levels with stationarity as the null, not as the alternative.

    ADF takes a unit root as its null, so failing to reject it is weak evidence and a
    marginal rejection is weaker still. The gasoline levels reject marginally under ADF,
    which on its own leaves the model-family choice resting on a knife edge a referee can
    push either way. KPSS reverses the null, so the two tests together either agree that a
    series is integrated or expose the ambiguity rather than hiding it.
    """
    required = {"log_PT", "log_ES"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")

    rows: list[dict[str, float | int | str | bool]] = []
    for country, column in (("PT", "log_PT"), ("ES", "log_ES")):
        series = pd.to_numeric(design[column], errors="coerce").dropna()
        for regression in ("c", "ct"):
            statistic, p_value, used_lag, _ = kpss(series, regression=regression, nlags="auto")
            rows.append(
                {
                    "product": product,
                    "country": country,
                    "value_column": column,
                    "regression": regression,
                    "nobs": int(len(series)),
                    "kpss_statistic": float(statistic),
                    "p_value": float(p_value),
                    "used_lag": int(used_lag),
                    # KPSS p-values are interpolated from a small table and clipped, so a
                    # reported 0.01 means "at most 0.01". Carry the verdict, not the number.
                    "rejects_stationarity_5pct": bool(float(p_value) < 0.05),
                }
            )
    return pd.DataFrame(rows)


def cointegrating_slope_test(
    design: pd.DataFrame, *, product: str, leads_lags: tuple[int, ...] = (2, 4, 8)
) -> pd.DataFrame:
    """Test whether the long-run slope is one, by dynamic OLS.

    Whether the raw PT-ES difference is the cointegrating combination turns on this slope
    being one, and how the price spread may be read depends on the answer. The first-stage
    OLS slope is super-consistent but its t-statistic is not standard normal, so it cannot
    support the test. Leads and lags of the differenced regressor absorb the endogeneity
    and restore standard inference.
    """
    required = {"log_PT", "log_ES"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")

    levels = design[["log_PT", "log_ES"]].apply(pd.to_numeric, errors="coerce").dropna().copy()
    levels["diff_log_ES"] = levels["log_ES"].diff()

    rows: list[dict[str, float | int | str | bool]] = []
    for span in leads_lags:
        frame = levels.copy()
        regressors = ["log_ES"]
        for shift in range(-span, span + 1):
            name = f"diff_log_ES_{shift:+d}"
            frame[name] = frame["diff_log_ES"].shift(-shift)
            regressors.append(name)
        frame = frame.dropna()
        design_matrix = sm.add_constant(frame[regressors], has_constant="add")
        fit = sm.OLS(frame["log_PT"], design_matrix).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
        test = fit.t_test("log_ES = 1")
        p_value = float(np.ravel(test.pvalue)[0])
        rows.append(
            {
                "product": product,
                "estimator": "DOLS",
                "leads_lags": int(span),
                "nobs": int(fit.nobs),
                "slope": float(fit.params["log_ES"]),
                "std_error": float(fit.bse["log_ES"]),
                "t_statistic_vs_one": float(np.ravel(test.tvalue)[0]),
                "p_value": p_value,
                "differs_from_one_5pct": bool(p_value < 0.05),
            }
        )
    return pd.DataFrame(rows)


def elasticity_unit_tests(design: pd.DataFrame, *, product: str) -> pd.DataFrame:
    """Test the contemporaneous elasticity against one rather than against zero.

    Regression output tests each coefficient against zero, which here asks whether
    Portuguese prices respond to Spanish prices at all. That was never in doubt. The
    threshold that carries economic content is one, which separates a price that
    under-transmits a Spanish move from one that overshoots it, and quoting only the
    change in the estimate conceals that the two phases sit on opposite sides of it.
    """
    fitted = fit_error_correction_model(design)
    model = cast(Any, fitted["model"])
    specifications = {
        "pre_transition": "diff_log_ES = 1",
        "post_transition": "diff_log_ES + diff_log_ES_x_post = 1",
    }
    rows: list[dict[str, float | int | str | bool]] = []
    for phase, specification in specifications.items():
        test = model.t_test(specification)
        estimate = float(np.ravel(test.effect)[0])
        p_value = float(np.ravel(test.pvalue)[0])
        rows.append(
            {
                "product": product,
                "phase": phase,
                "elasticity": estimate,
                "std_error": float(np.ravel(test.sd)[0]),
                "t_statistic_vs_one": float(np.ravel(test.tvalue)[0]),
                "p_value": p_value,
                "differs_from_one_5pct": bool(p_value < 0.05),
                "side": "below" if estimate < 1.0 else "above",
            }
        )
    return pd.DataFrame(rows)


def post_period_adjustment_stability(design: pd.DataFrame, *, product: str) -> pd.DataFrame:
    """Re-estimate the post-transition adjustment speed on subsets of the post period.

    Every interaction term in the error-correction model is identified off the post period
    alone, and that period is a fifth of the sample. It also contains the 2022 price
    episode, so a reader is entitled to ask whether faster adjustment is a property of the
    new regime or of that one year. Re-estimating without it, and on each half of the
    period, answers the question rather than leaving it standing.
    """
    if "date" not in design.columns:
        raise ValueError("Price design missing column: date")

    dates = pd.to_datetime(design["date"], errors="coerce")
    post = design["post"].astype(float) == 1.0
    midpoint = cast(pd.Timestamp, dates[post].quantile(0.5))

    subsets: dict[str, pd.Series] = {
        "full_post_period": pd.Series(True, index=design.index),
        "excluding_2022": dates.dt.year != 2022,
        "first_half_of_post": ~post | (dates <= midpoint),
        "second_half_of_post": ~post | (dates > midpoint),
    }

    rows: list[dict[str, float | int | str | bool]] = []
    for label, mask in subsets.items():
        subset = design.loc[mask]
        fitted = fit_error_correction_model(subset)
        model = cast(Any, fitted["model"])
        pre_speed = float(model.params["disequilibrium_lag"])
        post_speed = float(
            model.params["disequilibrium_lag"] + model.params["disequilibrium_lag_x_post"]
        )
        rows.append(
            {
                "product": product,
                "subset": label,
                "n_obs": int(model.nobs),
                "n_post": int((subset["post"].astype(float) == 1.0).sum()),
                "pre_adjustment_speed": pre_speed,
                "post_adjustment_speed": post_speed,
                "half_life_weeks": float(np.log(2.0) / -np.log1p(post_speed)),
                "speed_ratio": float(post_speed / pre_speed),
            }
        )
    return pd.DataFrame(rows)


def spread_stationarity_by_regime(design: pd.DataFrame, *, product: str) -> pd.DataFrame:
    """Run the spread unit-root test within each regime as well as on the pooled series.

    The spread mean shifts across the transition by tens of EUR per 1000 litres. An
    unmodelled level shift biases ADF towards not rejecting, so the pooled test understates
    mean reversion by construction and its verdict is not the one to quote. Testing within
    regimes removes the shift instead of arguing around it.
    """
    required = {"PT", "ES", "post"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")

    frame = pd.DataFrame(
        {
            "spread": pd.to_numeric(design["PT"], errors="coerce")
            - pd.to_numeric(design["ES"], errors="coerce"),
            "post": design["post"].astype(float),
        }
    ).dropna()

    segments = {
        "pooled": pd.Series(True, index=frame.index),
        "pre_transition": frame["post"] == 0.0,
        "post_transition": frame["post"] == 1.0,
    }

    rows: list[dict[str, float | int | str | bool]] = []
    for label, mask in segments.items():
        values = frame.loc[mask, "spread"]
        adf_statistic, p_value, used_lag, nobs, *_ = adfuller(values, autolag="AIC")
        rows.append(
            {
                "product": product,
                "segment": label,
                "nobs": int(len(values)),
                "mean_spread": float(values.mean()),
                "adf_statistic": float(adf_statistic),
                "p_value": float(p_value),
                "used_lag": int(used_lag),
                "adf_nobs": int(nobs),
                "stationary_5pct": bool(float(p_value) < 0.05),
            }
        )
    return pd.DataFrame(rows)


def weekly_coverage(prices: pd.DataFrame) -> pd.DataFrame:
    """Record how many weeks the bulletin actually published, and where the gaps are.

    The price models assume evenly spaced weekly observations, and the bulletin does not
    supply them: it skips weeks. A differenced observation spanning a gap is a two- or
    three-week change entered as one, and both the unit-root and the HAC lag structures
    read the index as even. The paper has to state the size of that, which means the
    count has to exist in the evidence rather than in a sentence.
    """
    required = {"date", "country", "product"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"Weekly prices missing columns: {sorted(missing)}")

    rows: list[dict[str, float | int | str]] = []
    for (country, product), group in prices.groupby(["country", "product"]):
        dates = pd.Series(sorted(pd.to_datetime(group["date"]).unique()))
        gaps = dates.diff().dt.days.dropna().astype(int)
        spanned = int((dates.iloc[-1] - dates.iloc[0]).days // 7) + 1
        rows.append(
            {
                "country": str(country),
                "product": str(product),
                "observed_weeks": int(len(dates)),
                "first_date": dates.iloc[0].date().isoformat(),
                "last_date": dates.iloc[-1].date().isoformat(),
                "weeks_spanned": spanned,
                "missing_weeks": int(spanned - len(dates)),
                "fortnight_gaps": int((gaps == 14).sum()),
                "three_week_gaps": int((gaps == 21).sum()),
                "longest_gap_days": int(gaps.max()) if len(gaps) else 0,
                "handling": "dropped, not interpolated",
            }
        )
    return pd.DataFrame(rows)


def gregory_hansen_test(
    design: pd.DataFrame,
    *,
    product: str,
    trim: float = 0.15,
    step: int = 5,
    lags: int = 4,
    n_simulations: int = 300,
    seed: int = 20260822,
) -> pd.DataFrame:
    """Test for cointegration when the long-run relation itself may shift.

    The two-step estimator holds one cointegrating vector across the whole sample while
    the second stage lets the adjustment speed break at the transition. That is an
    assumption, and it is the one a reader is most entitled to challenge, because the
    paper argues elsewhere that the transition changed the system. This test searches
    over break dates for the relation that best fits a shift in level and slope, and
    compares the resulting statistic with the distribution it would have under no
    cointegration at all.

    The null is simulated from independent random walks rather than read from a
    critical-value table, so the verdict can be reproduced without one. A fixed lag is
    used in the unit-root step because the statistic is a minimum over hundreds of
    candidate dates and an information criterion at each would change what is being
    minimised over.
    """
    required = {"log_PT", "log_ES", "date"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")

    frame = design[["date", "log_PT", "log_ES"]].dropna().reset_index(drop=True)
    n = len(frame)
    if n < 60:
        raise ValueError("Need at least 60 paired observations to search for a shift")

    y = frame["log_PT"].to_numpy(dtype=float)
    x = frame["log_ES"].to_numpy(dtype=float)
    lower, upper = int(np.floor(n * trim)), int(np.ceil(n * (1.0 - trim)))
    candidates = range(lower, upper, max(1, step))

    def min_adf(target: np.ndarray, regressor: np.ndarray) -> tuple[float, int]:
        best, best_index = np.inf, lower
        for index in candidates:
            shift = np.zeros(n)
            shift[index:] = 1.0
            columns = np.column_stack([np.ones(n), shift, regressor, regressor * shift])
            residuals = sm.OLS(target, columns).fit().resid
            statistic = adfuller(residuals, maxlag=lags, autolag=None)[0]
            if statistic < best:
                best, best_index = float(statistic), index
        return best, best_index

    observed, break_index = min_adf(y, x)

    rng = np.random.default_rng(seed)
    simulated = np.empty(n_simulations)
    for draw in range(n_simulations):
        walk_y = np.cumsum(rng.normal(0.0, 1.0, n))
        walk_x = np.cumsum(rng.normal(0.0, 1.0, n))
        simulated[draw] = min_adf(walk_y, walk_x)[0]

    # the statistic is a minimum, so rejection is in the left tail
    p_value = float(np.mean(simulated <= observed))
    return pd.DataFrame(
        [
            {
                "product": product,
                "model": "regime shift in level and slope",
                "nobs": int(n),
                "adf_statistic": observed,
                "break_date": str(pd.Timestamp(frame["date"].iloc[break_index]).date()),
                "break_fraction": float(break_index / n),
                "p_value": p_value,
                "null_5th_percentile": float(np.percentile(simulated, 5)),
                "cointegrated_with_shift_5pct": bool(p_value < 0.05),
                "n_candidates": int(len(list(candidates))),
                "n_simulations": int(n_simulations),
                "unit_root_lags": int(lags),
            }
        ]
    )


def second_break_test(
    design: pd.DataFrame,
    *,
    product: str,
    second_cutoff: str | pd.Timestamp = "2022-03-01",
    maxlags: int = 8,
) -> pd.DataFrame:
    """Ask whether the price relation breaks again when the supply shock arrives.

    The physical arm partitions the period into four phases; the price arm imposes one
    break, at the closure. If the March 2022 disruption moved the price relation as well,
    the single-break model attributes that movement to the closure, because everything
    after May 2021 is one regime by construction. Adding the second date and testing its
    terms is the only way to find out, and a null result is as informative as a positive
    one here.
    """
    required = {"log_PT", "log_ES", "diff_log_PT", "diff_log_ES", "post", "date"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")

    levels = design[["log_PT", "log_ES"]].apply(pd.to_numeric, errors="coerce").dropna()
    long_run = sm.OLS(
        levels["log_PT"], sm.add_constant(levels[["log_ES"]], has_constant="add")
    ).fit()

    frame = design.copy()
    frame["disequilibrium"] = np.nan
    frame.loc[levels.index, "disequilibrium"] = np.asarray(long_run.resid, dtype=float)
    frame["disequilibrium_lag"] = frame["disequilibrium"].shift(1)
    frame["stress"] = (pd.to_datetime(frame["date"]) >= pd.Timestamp(second_cutoff)).astype(float)
    frame = frame.dropna(
        subset=["diff_log_PT", "diff_log_ES", "disequilibrium_lag", "post", "stress"]
    ).copy()

    frame["diff_log_ES_x_post"] = frame["diff_log_ES"] * frame["post"]
    frame["disequilibrium_lag_x_post"] = frame["disequilibrium_lag"] * frame["post"]
    frame["diff_log_ES_x_stress"] = frame["diff_log_ES"] * frame["stress"]
    frame["disequilibrium_lag_x_stress"] = frame["disequilibrium_lag"] * frame["stress"]

    regressors = [
        "disequilibrium_lag",
        "disequilibrium_lag_x_post",
        "disequilibrium_lag_x_stress",
        "diff_log_ES",
        "diff_log_ES_x_post",
        "diff_log_ES_x_stress",
        "post",
        "stress",
    ]
    x = sm.add_constant(frame[regressors], has_constant="add")
    model = sm.OLS(frame["diff_log_PT"], x).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})

    joint = model.f_test("disequilibrium_lag_x_stress = 0, diff_log_ES_x_stress = 0, stress = 0")
    joint_f = float(np.ravel(joint.fvalue)[0])
    joint_p = float(np.ravel(joint.pvalue)[0])

    def record(term: str, estimate: float, std_error: float, p_value: float) -> dict[str, object]:
        return {
            "product": product,
            "second_break": str(pd.Timestamp(second_cutoff).date()),
            "term": term,
            "estimate": estimate,
            "std_error": std_error,
            "p_value": p_value,
            "nobs": int(model.nobs),
            "joint_f_statistic": joint_f,
            "joint_p_value": joint_p,
            "second_break_detected_5pct": bool(joint_p < 0.05),
        }

    rows: list[dict[str, object]] = [
        record(
            term,
            float(model.params[term]),
            float(model.bse[term]),
            float(model.pvalues[term]),
        )
        for term in ("disequilibrium_lag_x_stress", "diff_log_ES_x_stress", "stress")
    ]

    # The interaction terms are differences. What the paper quotes is the level in each
    # regime, and a level that exists only as arithmetic on three coefficients cannot be
    # checked against the evidence, so each is recorded here with its own standard error.
    levels = {
        "elasticity_pre_closure": "diff_log_ES = 0",
        "elasticity_transition": "diff_log_ES + diff_log_ES_x_post = 0",
        "elasticity_stress_onward": ("diff_log_ES + diff_log_ES_x_post + diff_log_ES_x_stress = 0"),
        "adjustment_pre_closure": "disequilibrium_lag = 0",
        "adjustment_transition": "disequilibrium_lag + disequilibrium_lag_x_post = 0",
        "adjustment_stress_onward": (
            "disequilibrium_lag + disequilibrium_lag_x_post + disequilibrium_lag_x_stress = 0"
        ),
    }
    for name, specification in levels.items():
        wald = model.t_test(specification)
        rows.append(
            record(
                name,
                float(np.ravel(wald.effect)[0]),
                float(np.ravel(wald.sd)[0]),
                float(np.ravel(wald.pvalue)[0]),
            )
        )
    return pd.DataFrame(rows)


#: Neighbours priced in the same bulletin that closed no refinery in May 2021. They are
#: the comparison for asking whether the Portuguese adjustment change is Portuguese.
PLACEBO_COUNTRIES: tuple[str, ...] = ("FR", "IT", "DE", "BE")


def _adjustment_speeds(
    prices: pd.DataFrame, *, home: str, product: str, cutoff: str, end: str | None = None
) -> dict[str, float]:
    """Fit the error-correction model for one country pair and return its two speeds."""
    work = prices.loc[prices["country"].isin([home, "ES"])].copy()
    work["country"] = work["country"].replace({home: "PT"})
    if end is not None:
        work = work.loc[pd.to_datetime(work["date"]) < pd.Timestamp(end)]
    design = price_comovement_design(work, product=product, cutoff=cutoff)
    model = cast(Any, fit_error_correction_model(design)["model"])
    pre = float(model.params["disequilibrium_lag"])
    post = pre + float(model.params["disequilibrium_lag_x_post"])
    return {
        "pre_adjustment_speed": pre,
        "post_adjustment_speed": post,
        "speed_ratio": post / pre if pre else float("nan"),
        "interaction_p_value": float(model.pvalues["disequilibrium_lag_x_post"]),
        "n_obs": float(model.nobs),
    }


def cross_country_placebo(
    prices: pd.DataFrame,
    *,
    product: str = "diesel",
    cutoff: str = "2021-05-01",
    countries: tuple[str, ...] = PLACEBO_COUNTRIES,
) -> pd.DataFrame:
    """Run the same break on countries that closed no refinery.

    The paper reads a faster adjustment speed after May 2021 as a loss of domestic price
    insulation. An alternative reading is that the disequilibrium term simply became more
    volatile everywhere after 2021, in which case every European pair priced against Spain
    would show the same thing and the Portuguese result would be a date effect. Running the
    identical specification on neighbours that closed nothing separates the two, and it is
    the cheapest test available because the bulletin already prices every member state.
    """
    rows: list[dict[str, object]] = []
    for home in ("PT", *countries):
        available = set(prices["country"].unique())
        if home not in available or "ES" not in available:
            continue
        speeds = _adjustment_speeds(prices, home=home, product=product, cutoff=cutoff)
        rows.append(
            {
                "pair": f"{home}-ES",
                "product": product,
                "break_date": cutoff,
                "closed_a_refinery": home == "PT",
                **speeds,
            }
        )
    return pd.DataFrame(rows)


def false_break_placebo(
    prices: pd.DataFrame,
    *,
    product: str = "diesel",
    dates: tuple[str, ...] = (
        "2011-05-01",
        "2013-05-01",
        "2015-05-01",
        "2017-05-01",
        "2019-05-01",
    ),
    real_break: str = "2021-05-01",
) -> pd.DataFrame:
    """Test breaks at dates where nothing happened, on data that cannot contain the real one.

    A false break placed on the full sample is not a placebo: everything after a 2018 date
    includes the 2021 closure, so it recovers a diluted version of the real effect and looks
    like a finding. Each false break here is estimated on the pre-closure sample only, which
    is the only way the test can come out negative when it should.
    """
    rows: list[dict[str, object]] = []
    for date in dates:
        speeds = _adjustment_speeds(prices, home="PT", product=product, cutoff=date, end=real_break)
        rows.append(
            {
                "break_date": date,
                "product": product,
                "sample_ends": real_break,
                "is_real_break": False,
                **speeds,
            }
        )
    speeds = _adjustment_speeds(prices, home="PT", product=product, cutoff=real_break)
    rows.append(
        {
            "break_date": real_break,
            "product": product,
            "sample_ends": "",
            "is_real_break": True,
            **speeds,
        }
    )
    return pd.DataFrame(rows)


def johansen_rank_test(
    design: pd.DataFrame, *, product: str, lag_orders: tuple[int, ...] = (1, 2, 4)
) -> pd.DataFrame:
    """Cross-check the single-equation cointegration verdict with a system estimator.

    Engle--Granger picks one variable as the dependent one and conditions the second
    stage on a first-stage residual. Johansen treats the two series symmetrically and
    estimates the cointegrating rank instead of assuming it, so it can disagree in two
    ways that matter: it can fail to find a relation the two-step estimator claimed, and
    it can find full rank, which would mean the levels were stationary all along and the
    error-correction form was never needed.
    """
    required = {"log_PT", "log_ES"}
    missing = required - set(design.columns)
    if missing:
        raise ValueError(f"Price design missing columns: {sorted(missing)}")

    levels = design[["log_PT", "log_ES"]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(levels) < 30:
        raise ValueError("Need at least 30 paired levels for a rank test")

    rows: list[dict[str, float | int | str | bool]] = []
    for lags in lag_orders:
        result = coint_johansen(levels.to_numpy(dtype=float), det_order=0, k_ar_diff=int(lags))
        vector = np.real(result.evec[:, 0])
        normalised = float(-vector[1] / vector[0]) if vector[0] else float("nan")
        for rank, label in enumerate(("r = 0", "r <= 1")):
            trace = float(result.lr1[rank])
            critical = float(result.cvt[rank][1])
            rows.append(
                {
                    "product": product,
                    "lags": int(lags),
                    "nobs": int(len(levels)),
                    "null_hypothesis": label,
                    "trace_statistic": trace,
                    "critical_value_5pct": critical,
                    "rejected_5pct": bool(trace > critical),
                    "normalised_slope": normalised,
                }
            )
    return pd.DataFrame(rows)


#: The seaborne crude embargo bites on 5 December 2022 for every member state at once,
#: which makes it the natural second date to run the cross-country comparison at.
EMBARGO_DATE: str = "2022-12-05"


def placebo_by_break_date(
    prices: pd.DataFrame,
    *,
    product: str = "diesel",
    break_dates: tuple[str, ...] = ("2021-05-01", EMBARGO_DATE),
    countries: tuple[str, ...] = PLACEBO_COUNTRIES,
) -> pd.DataFrame:
    """Run the cross-country comparison at more than one candidate date.

    A single date cannot tell a country-specific event from a common one. The Portuguese
    closure falls in May 2021 and the seaborne crude embargo in December 2022, and the
    two dates are nineteen months apart, so running both separates a response that only
    Portugal shows from one that every pair priced against Spain shows. Which countries
    move at which date is the whole content of the test.
    """
    rows: list[dict[str, object]] = []
    available = set(prices["country"].unique())
    for cutoff in break_dates:
        for home in ("PT", *countries):
            if home not in available or "ES" not in available:
                continue
            speeds = _adjustment_speeds(prices, home=home, product=product, cutoff=cutoff)
            rows.append(
                {
                    "pair": f"{home}-ES",
                    "product": product,
                    "break_date": cutoff,
                    "closed_a_refinery_in_may_2021": home == "PT",
                    **speeds,
                }
            )
    return pd.DataFrame(rows)


def phase_adjustment_speeds(
    prices: pd.DataFrame,
    *,
    home: str,
    product: str = "diesel",
    first_break: str = "2021-05-01",
    second_break: str = EMBARGO_DATE,
    maxlags: int = 8,
) -> pd.DataFrame:
    """Split the post period at the embargo and report the speed in each of three phases.

    A ratio computed against a single break date averages whatever happened after it. If
    the Portuguese change belongs to the closure it should appear between May 2021 and the
    embargo; if it belongs to the embargo it should appear only afterwards, and so should
    every other country's.
    """
    work = prices.loc[prices["country"].isin([home, "ES"])].copy()
    work["country"] = work["country"].replace({home: "PT"})
    design = price_comovement_design(work, product=product, cutoff=first_break)

    levels = design[["log_PT", "log_ES"]].apply(pd.to_numeric, errors="coerce").dropna()
    long_run = sm.OLS(
        levels["log_PT"], sm.add_constant(levels[["log_ES"]], has_constant="add")
    ).fit()
    frame = design.copy()
    frame["disequilibrium"] = np.nan
    frame.loc[levels.index, "disequilibrium"] = np.asarray(long_run.resid, dtype=float)
    frame["disequilibrium_lag"] = frame["disequilibrium"].shift(1)
    frame["late"] = (pd.to_datetime(frame["date"]) >= pd.Timestamp(second_break)).astype(float)
    frame = frame.dropna(
        subset=["diff_log_PT", "diff_log_ES", "disequilibrium_lag", "post", "late"]
    ).copy()
    frame["d_x_post"] = frame["disequilibrium_lag"] * frame["post"]
    frame["d_x_late"] = frame["disequilibrium_lag"] * frame["late"]
    frame["e_x_post"] = frame["diff_log_ES"] * frame["post"]
    frame["e_x_late"] = frame["diff_log_ES"] * frame["late"]
    columns = [
        "disequilibrium_lag",
        "d_x_post",
        "d_x_late",
        "diff_log_ES",
        "e_x_post",
        "e_x_late",
        "post",
        "late",
    ]
    model = sm.OLS(frame["diff_log_PT"], sm.add_constant(frame[columns], has_constant="add")).fit(
        cov_type="HAC", cov_kwds={"maxlags": maxlags}
    )
    embargo_test = model.t_test("d_x_late = 0")
    embargo_p = float(np.ravel(embargo_test.pvalue)[0])

    phases = {
        "before_closure": "disequilibrium_lag = 0",
        "closure_to_embargo": "disequilibrium_lag + d_x_post = 0",
        "embargo_onward": "disequilibrium_lag + d_x_post + d_x_late = 0",
    }
    rows: list[dict[str, object]] = []
    for phase, specification in phases.items():
        test = model.t_test(specification)
        rows.append(
            {
                "pair": f"{home}-ES",
                "product": product,
                "phase": phase,
                "adjustment_speed": float(np.ravel(test.effect)[0]),
                "std_error": float(np.ravel(test.sd)[0]),
                "p_value": float(np.ravel(test.pvalue)[0]),
                "embargo_interaction_p_value": embargo_p,
                "n_obs": int(model.nobs),
            }
        )
    return pd.DataFrame(rows)
