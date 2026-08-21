from __future__ import annotations

import pandas as pd


def assert_unique(df: pd.DataFrame, columns: list[str]) -> None:
    """Raise when a dataframe key is not unique."""
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing uniqueness columns: {missing}")
    if df.duplicated(columns).any():
        raise ValueError(f"Duplicate observations for key {columns}")


def assert_nonnegative(df: pd.DataFrame, columns: list[str]) -> None:
    """Reject negative physical quantities."""
    for column in columns:
        if column not in df.columns:
            continue
        values = pd.to_numeric(df[column], errors="coerce")
        if (values.dropna() < 0).any():
            raise ValueError(f"Negative values found in {column}")


def assert_year_coverage(df: pd.DataFrame, start: int, end: int, *, year_col: str = "year") -> None:
    """Check that each year in a requested interval occurs at least once."""
    years = set(pd.to_numeric(df[year_col], errors="coerce").dropna().astype(int))
    missing = sorted(set(range(start, end + 1)) - years)
    if missing:
        raise ValueError(f"Missing years: {missing}")


#: The four balance terms. Trade is cross-checked between sources elsewhere; output and
#: demand were not cross-checked anywhere, which is the gap this closes.
BALANCE_FLOWS: tuple[str, ...] = (
    "imports_kt",
    "exports_kt",
    "demand_kt",
    "refinery_output_kt",
)


def reconcile_monthly_to_annual(
    monthly: pd.DataFrame,
    annual: pd.DataFrame,
    *,
    flows: tuple[str, ...] = BALANCE_FLOWS,
    tolerance_pct: float = 5.0,
) -> pd.DataFrame:
    """Aggregate the monthly panel to years and compare it with the annual panel.

    The two arms of this study measure the same physical quantities from different
    sources: the monthly event models read JODI, the annual balance reads Eurostat.
    Trade was reconciled between them, but refinery output and demand were not, and
    refinery output is the outcome behind the monthly phase estimates and the headline
    coverage ratio. Coverage checks establish that months are present; they say nothing
    about whether the two sources agree on what those months contain.

    Only complete years are compared, since a partial year would show as a shortfall
    that is an artefact of the calendar rather than a disagreement between sources.
    """
    for frame, name in ((monthly, "monthly"), (annual, "annual")):
        missing = ({"product", *flows} - set(frame.columns)) - {"year"}
        if missing:
            raise ValueError(f"{name} panel missing columns: {sorted(missing)}")
    if "date" not in monthly.columns and "year" not in monthly.columns:
        raise ValueError("monthly panel missing columns: ['date']")

    work = monthly.copy()
    if "year" not in work.columns:
        work["year"] = pd.to_datetime(work["date"], errors="coerce").dt.year
    work = work.dropna(subset=["year"])
    work["year"] = work["year"].astype(int)

    observed = work.groupby(["product", "year"]).size().rename("months_observed")
    rolled = work.groupby(["product", "year"])[list(flows)].sum().join(observed).reset_index()
    complete = rolled.loc[rolled["months_observed"] == 12].drop(columns="months_observed")

    merged = complete.merge(
        annual[["product", "year", *flows]],
        on=["product", "year"],
        suffixes=("_monthly", "_annual"),
    )

    records: list[dict[str, float | int | str | bool]] = []
    for _, row in merged.iterrows():
        for flow in flows:
            monthly_value = float(row[f"{flow}_monthly"])
            annual_value = float(row[f"{flow}_annual"])
            difference = monthly_value - annual_value
            percent = (difference / annual_value * 100.0) if annual_value else float("nan")
            records.append(
                {
                    "product": str(row["product"]),
                    "year": int(row["year"]),
                    "flow": flow.removesuffix("_kt"),
                    "monthly_source_kt": monthly_value,
                    "annual_source_kt": annual_value,
                    "difference_kt": difference,
                    "difference_pct": percent,
                    "within_tolerance": bool(abs(percent) <= tolerance_pct)
                    if pd.notna(percent)
                    else False,
                }
            )
    return pd.DataFrame(records)


def monthly_annual_agreement_summary(reconciliation: pd.DataFrame) -> pd.DataFrame:
    """Reduce the cell-level comparison to one row per flow.

    A reader deciding how much weight the monthly arm carries needs the worst case per
    flow, not an average over cells that hides it.
    """
    required = {"flow", "difference_pct", "within_tolerance"}
    missing = required - set(reconciliation.columns)
    if missing:
        raise ValueError(f"Reconciliation missing columns: {sorted(missing)}")

    rows: list[dict[str, float | int | str]] = []
    for flow, group in reconciliation.groupby("flow"):
        absolute = group["difference_pct"].abs()
        worst = group.loc[absolute.idxmax()] if absolute.notna().any() else None
        rows.append(
            {
                "flow": str(flow),
                "n_cells": int(len(group)),
                "median_abs_pct": float(absolute.median()),
                "max_abs_pct": float(absolute.max()),
                "share_within_tolerance": float(group["within_tolerance"].mean()),
                "worst_year": int(worst["year"]) if worst is not None else 0,  # type: ignore[arg-type]
                "worst_product": str(worst["product"]) if worst is not None else "",
            }
        )
    return pd.DataFrame(rows).sort_values("max_abs_pct", ascending=False).reset_index(drop=True)
