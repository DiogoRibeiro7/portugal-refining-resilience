from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint

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
