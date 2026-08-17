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
