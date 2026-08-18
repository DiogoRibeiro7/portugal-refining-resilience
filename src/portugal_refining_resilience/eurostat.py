from __future__ import annotations

from math import prod
from typing import Any

import numpy as np
import pandas as pd
import requests

from .metrics import add_supply_metrics

_PRODUCT_ALIASES: dict[str, set[str]] = {
    "diesel": {
        "gas oil and diesel oil",
        "gas/diesel oil",
        "gas oil",
        "diesel",
    },
    "gasoline": {
        "motor gasoline",
        "gasoline",
    },
}

_BALANCE_ALIASES: dict[str, set[str]] = {
    "imports": {"imports"},
    "exports": {"exports"},
    "demand": {
        "gross inland deliveries - observed",
        "gross inland deliveries",
        "final consumption",
    },
    "refinery_output": {
        "refinery output",
        "production",
        "transformation output - oil refineries",
        # nrg_bal code TO_RPI_RO, the label Eurostat actually ships.
        "transformation output - refineries and petrochemical industry - refinery output",
    },
}

_UNIT_TO_KT: dict[str, float] = {
    "thousand tonnes": 1.0,
    "1000 tonnes": 1.0,
    "kt": 1.0,
    "tonnes": 0.001,
}


def _normalise_label(value: object) -> str:
    return " ".join(str(value).strip().lower().replace("\n", " ").split())


def _first_existing(columns: pd.Index, candidates: tuple[str, ...]) -> str:
    normalised = {str(column).lower(): str(column) for column in columns}
    for candidate in candidates:
        if candidate in normalised:
            return normalised[candidate]
    raise ValueError(f"Missing expected Eurostat columns. Need one of: {candidates}")


def fetch_jsonstat(
    dataset: str,
    *,
    params: dict[str, str | list[str]] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Fetch a Eurostat dissemination API dataset in JSON-stat format.

    A parameter may carry a list, which the dissemination API reads as a repeated
    key, so a single request can select several countries, products or balances.
    """
    if not dataset.replace("_", "").isalnum():
        raise ValueError(f"Unsafe Eurostat dataset code: {dataset}")
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
    response = requests.get(url, params=params or {}, timeout=timeout)
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload


def jsonstat_to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    """Decode Eurostat JSON-stat 2 observations into a tidy dataframe.

    Both sparse dictionary and dense list ``value`` representations are supported.
    Dimension code and human-readable label columns are emitted.
    """
    ids = list(payload.get("id", []))
    sizes = list(payload.get("size", []))
    dimensions = payload.get("dimension", {})
    if not ids or not sizes or len(ids) != len(sizes):
        raise ValueError("Malformed JSON-stat payload: missing id/size dimensions")

    ordered_codes: list[list[str]] = []
    labels: dict[str, dict[str, str]] = {}
    for dim in ids:
        category = dimensions[dim]["category"]
        index = category.get("index", {})
        if isinstance(index, list):
            codes = list(index)
        else:
            codes = [code for code, _ in sorted(index.items(), key=lambda item: item[1])]
        ordered_codes.append(codes)
        labels[dim] = category.get("label", {})

    values = payload.get("value", {})
    total = prod(sizes)

    # Row-major strides let a flat index be decoded directly, so the work scales with
    # the number of observations rather than the size of the full dimension grid. The
    # nrg_cb_oil grid runs to tens of millions of cells for a handful of real series.
    strides: list[int] = [1] * len(sizes)
    for axis in range(len(sizes) - 2, -1, -1):
        strides[axis] = strides[axis + 1] * sizes[axis + 1]

    if isinstance(values, list):
        observations: list[tuple[int, Any]] = [
            (index, value) for index, value in enumerate(values) if value is not None
        ]
    else:
        observations = sorted(
            (int(index), value) for index, value in values.items() if value is not None
        )

    rows: list[dict[str, Any]] = []
    for flat_index, value in observations:
        if not 0 <= flat_index < total:
            raise ValueError(f"JSON-stat index {flat_index} outside the declared grid of {total}")
        row: dict[str, Any] = {"value": value}
        for dim, stride, size, codes in zip(ids, strides, sizes, ordered_codes, strict=True):
            code = codes[(flat_index // stride) % size]
            row[dim] = code
            row[f"{dim}_label"] = labels[dim].get(code, code)
        rows.append(row)
    return pd.DataFrame(rows)


def canonicalise_oil_balance(df: pd.DataFrame, *, source: str = "Eurostat") -> pd.DataFrame:
    """Select diesel/gasoline annual balance terms from a Eurostat oil-balance frame."""
    country_col = _first_existing(df.columns, ("geo", "country"))
    time_col = _first_existing(df.columns, ("time", "year"))
    product_col = _first_existing(df.columns, ("siec", "product"))
    product_label_col = "siec_label" if "siec_label" in df.columns else product_col
    balance_col = _first_existing(df.columns, ("nrg_bal", "balance", "flow"))
    balance_label_col = "nrg_bal_label" if "nrg_bal_label" in df.columns else balance_col
    unit_col = _first_existing(df.columns, ("unit_label", "unit"))

    records: list[dict[str, object]] = []
    for row in df.to_dict("records"):
        product_label = _normalise_label(row[product_label_col])
        product = next(
            (
                canonical
                for canonical, labels in _PRODUCT_ALIASES.items()
                if product_label in labels or _normalise_label(row[product_col]) in labels
            ),
            None,
        )
        balance_label = _normalise_label(row[balance_label_col])
        flow = next(
            (
                canonical
                for canonical, labels in _BALANCE_ALIASES.items()
                if balance_label in labels or _normalise_label(row[balance_col]) in labels
            ),
            None,
        )
        unit = _normalise_label(row[unit_col])
        if product is None or flow is None:
            continue
        if unit not in _UNIT_TO_KT:
            continue
        value = pd.to_numeric(pd.Series([row["value"]]), errors="coerce").iloc[0]
        if pd.isna(value):
            continue
        records.append(
            {
                "year": int(row[time_col]),
                "country": str(row[country_col]),
                "product": product,
                "flow": flow,
                "value_kt": float(value) * _UNIT_TO_KT[unit],
                "source": source,
            }
        )
    return pd.DataFrame(records)


def build_balance_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot canonical Eurostat balance terms and calculate physical ratios."""
    required = {"year", "country", "product", "flow", "value_kt"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Eurostat canonical balance missing columns: {sorted(missing)}")
    panel = (
        df.pivot_table(
            index=["year", "country", "product"],
            columns="flow",
            values="value_kt",
            aggfunc="sum",
        )
        .rename(
            columns={
                "imports": "imports_kt",
                "exports": "exports_kt",
                "demand": "demand_kt",
                "refinery_output": "refinery_output_kt",
            }
        )
        .reset_index()
    )
    if {"imports_kt", "exports_kt", "demand_kt"}.issubset(panel.columns):
        panel = add_supply_metrics(panel)
    if {"imports_kt", "exports_kt", "demand_kt", "refinery_output_kt"}.issubset(panel.columns):
        panel["balance_residual_kt"] = (
            panel["refinery_output_kt"] + panel["imports_kt"] - panel["exports_kt"]
        ) - panel["demand_kt"]
        panel["balance_residual_to_demand_ratio"] = panel["balance_residual_kt"] / panel[
            "demand_kt"
        ].replace(0, np.nan)
    return panel
