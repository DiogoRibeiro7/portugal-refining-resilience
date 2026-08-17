from __future__ import annotations

import numpy as np
import pandas as pd


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide two numeric series and return NaN for zero/invalid denominators."""
    num = pd.to_numeric(numerator, errors="coerce").astype(float)
    den = pd.to_numeric(denominator, errors="coerce").astype(float)
    return pd.Series(np.where(den != 0, num / den, np.nan), index=numerator.index)


def add_supply_metrics(panel: pd.DataFrame) -> pd.DataFrame:
    """Add transparent trade/dependence metrics to an annual product panel."""
    required = {"imports_kt", "exports_kt", "demand_kt"}
    missing = required - set(panel.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    out = panel.copy()
    out["net_imports_kt"] = out["imports_kt"] - out["exports_kt"]
    out["gross_import_dependence"] = safe_ratio(out["imports_kt"], out["demand_kt"])
    out["net_import_dependence"] = safe_ratio(out["net_imports_kt"], out["demand_kt"])
    out["export_to_demand"] = safe_ratio(out["exports_kt"], out["demand_kt"])
    if "refinery_output_kt" in out.columns:
        out["domestic_output_coverage"] = safe_ratio(out["refinery_output_kt"], out["demand_kt"])
    return out


def add_yoy(df: pd.DataFrame, value_columns: list[str], *, group: str = "product") -> pd.DataFrame:
    """Add year-over-year percentage changes within product."""
    out = df.sort_values([group, "year"]).copy()
    for column in value_columns:
        if column not in out.columns:
            continue
        out[f"{column}_yoy_pct"] = out.groupby(group)[column].pct_change(fill_method=None) * 100.0
    return out


def event_window_summary(
    df: pd.DataFrame,
    *,
    value_column: str,
    event_year: int,
    pre_years: int = 5,
    post_years: int = 3,
) -> pd.DataFrame:
    """Summarise mean levels around an event without assigning causality."""
    if pre_years < 1 or post_years < 1:
        raise ValueError("pre_years and post_years must be positive")
    records: list[dict[str, float | int | str]] = []
    for product_name, group in df.groupby("product"):
        pre = group.loc[group["year"].between(event_year - pre_years, event_year - 1), value_column]
        post = group.loc[
            group["year"].between(event_year + 1, event_year + post_years), value_column
        ]
        pre_mean = float(pre.mean()) if not pre.empty else float("nan")
        post_mean = float(post.mean()) if not post.empty else float("nan")
        pct_difference = 100 * (post_mean / pre_mean - 1) if pre_mean != 0 else float("nan")
        records.append(
            {
                "product": str(product_name),
                "event_year": event_year,
                "value_column": value_column,
                "pre_mean": pre_mean,
                "post_mean": post_mean,
                "difference": post_mean - pre_mean,
                "pct_difference": pct_difference,
            }
        )
    return pd.DataFrame(records)
