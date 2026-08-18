from __future__ import annotations

import numpy as np
import pandas as pd

#: Share metrics produced by :func:`add_supply_metrics`. Their differences are
#: ratio differences, not already-scaled percentage points.
SUPPLY_RATIO_COLUMNS: frozenset[str] = frozenset(
    {
        "gross_import_dependence",
        "net_import_to_demand_ratio",
        "export_to_demand",
        "refinery_output_to_demand_ratio",
    }
)


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide two numeric series and return NaN for zero/invalid denominators."""
    num = pd.to_numeric(numerator, errors="coerce").astype(float)
    den = pd.to_numeric(denominator, errors="coerce").astype(float)
    return pd.Series(np.where(den != 0, num / den, np.nan), index=numerator.index)


def add_supply_metrics(panel: pd.DataFrame) -> pd.DataFrame:
    """Add transparent trade and physical-balance ratios to an annual product panel."""
    required = {"imports_kt", "exports_kt", "demand_kt"}
    missing = required - set(panel.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    out = panel.copy()
    out["net_imports_kt"] = out["imports_kt"] - out["exports_kt"]
    out["gross_import_dependence"] = safe_ratio(out["imports_kt"], out["demand_kt"])
    out["net_import_to_demand_ratio"] = safe_ratio(out["net_imports_kt"], out["demand_kt"])
    out["export_to_demand"] = safe_ratio(out["exports_kt"], out["demand_kt"])
    if "refinery_output_kt" in out.columns:
        out["refinery_output_to_demand_ratio"] = safe_ratio(
            out["refinery_output_kt"], out["demand_kt"]
        )
    return out


def add_yoy(
    df: pd.DataFrame,
    value_columns: list[str],
    *,
    group: str = "product",
    allow_signed_percentage: bool = False,
) -> pd.DataFrame:
    """Add year-over-year changes within product.

    Percentage changes are skipped for signed series unless explicitly allowed,
    because crossings around zero do not have a stable percentage interpretation.
    """
    out = df.sort_values([group, "year"]).copy()
    for column in value_columns:
        if column not in out.columns:
            continue
        lag = out.groupby(group)[column].shift(1)
        out[f"{column}_yoy_change"] = out[column] - lag
        has_nonpositive = pd.to_numeric(lag, errors="coerce").le(0).any()
        has_negative_current = pd.to_numeric(out[column], errors="coerce").lt(0).any()
        if allow_signed_percentage or not (has_nonpositive or has_negative_current):
            out[f"{column}_yoy_pct"] = (
                out.groupby(group)[column].pct_change(fill_method=None) * 100.0
            )
    return out


def benchmark_deviation(
    df: pd.DataFrame,
    *,
    value_column: str,
    target_year: int,
    baseline_start: int,
    baseline_end: int,
    group: str = "product",
) -> pd.DataFrame:
    """Compare a target year with an explicit baseline using robust diagnostics."""
    records: list[dict[str, float | int | str]] = []
    for group_name, group_df in df.groupby(group):
        baseline = pd.to_numeric(
            group_df.loc[group_df["year"].between(baseline_start, baseline_end), value_column],
            errors="coerce",
        ).dropna()
        target = pd.to_numeric(
            group_df.loc[group_df["year"] == target_year, value_column], errors="coerce"
        ).dropna()
        target_value = float(target.iloc[0]) if len(target) == 1 else float("nan")
        mean = float(baseline.mean()) if not baseline.empty else float("nan")
        std = float(baseline.std(ddof=1)) if len(baseline) > 1 else float("nan")
        median = float(baseline.median()) if not baseline.empty else float("nan")
        mad = float((baseline - median).abs().median()) if not baseline.empty else float("nan")
        percentile = (
            float((baseline.le(target_value).sum() / len(baseline)) * 100)
            if len(baseline) and pd.notna(target_value)
            else float("nan")
        )
        records.append(
            {
                group: str(group_name),
                "value_column": value_column,
                "target_year": target_year,
                "target_value": target_value,
                "baseline_start": baseline_start,
                "baseline_end": baseline_end,
                "baseline_n": int(len(baseline)),
                "baseline_mean": mean,
                "baseline_std": std,
                "z_score": (target_value - mean) / std if std > 0 else float("nan"),
                "baseline_median": median,
                "baseline_mad": mad,
                "robust_z_score": (target_value - median) / (1.4826 * mad)
                if mad > 0
                else float("nan"),
                "empirical_percentile": percentile,
            }
        )
    return pd.DataFrame(records)


def event_window_summary(
    df: pd.DataFrame,
    *,
    value_column: str,
    event_year: int,
    pre_years: int = 5,
    post_years: int = 3,
    percent_change_columns: set[str] | None = None,
    ratio_columns: set[str] | frozenset[str] | None = None,
) -> pd.DataFrame:
    """Summarise mean levels around an event without assigning causality.

    ``difference`` is always expressed in the units of ``value_column``. For share
    metrics that means a ratio difference, so ``difference_percentage_points`` is
    reported alongside it to remove any ambiguity about scaling.
    """
    if pre_years < 1 or post_years < 1:
        raise ValueError("pre_years and post_years must be positive")
    records: list[dict[str, float | int | str]] = []
    percent_change_columns = percent_change_columns or {
        "exports_kt",
        "imports_kt",
        "demand_kt",
        "refinery_output_kt",
    }
    ratio_columns = SUPPLY_RATIO_COLUMNS if ratio_columns is None else ratio_columns
    is_ratio = value_column in ratio_columns or value_column.endswith("_ratio")
    for product_name, group in df.groupby("product"):
        pre = group.loc[group["year"].between(event_year - pre_years, event_year - 1), value_column]
        post = group.loc[
            group["year"].between(event_year + 1, event_year + post_years), value_column
        ]
        pre_mean = float(pre.mean()) if not pre.empty else float("nan")
        post_mean = float(post.mean()) if not post.empty else float("nan")
        pct_difference = (
            100 * (post_mean / pre_mean - 1)
            if value_column in percent_change_columns and pre_mean > 0
            else float("nan")
        )
        difference = post_mean - pre_mean
        records.append(
            {
                "product": str(product_name),
                "event_year": event_year,
                "value_column": value_column,
                "pre_mean": pre_mean,
                "post_mean": post_mean,
                "difference": difference,
                "difference_unit": "ratio" if is_ratio else "level",
                "difference_percentage_points": difference * 100.0 if is_ratio else float("nan"),
                "pct_difference": pct_difference,
            }
        )
    return pd.DataFrame(records)
