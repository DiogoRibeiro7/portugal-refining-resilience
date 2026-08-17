from __future__ import annotations

from itertools import product
from math import prod
from typing import Any

import pandas as pd
import requests


def fetch_jsonstat(
    dataset: str,
    *,
    params: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Fetch a Eurostat dissemination API dataset in JSON-stat format."""
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
    rows: list[dict[str, Any]] = []
    total = prod(sizes)
    for flat_index, coordinates in enumerate(product(*[range(size) for size in sizes])):
        if flat_index >= total:
            break
        if isinstance(values, list):
            value = values[flat_index] if flat_index < len(values) else None
        else:
            value = values.get(str(flat_index))
        if value is None:
            continue
        row: dict[str, Any] = {"value": value}
        for dim, coord, codes in zip(ids, coordinates, ordered_codes, strict=True):
            code = codes[coord]
            row[dim] = code
            row[f"{dim}_label"] = labels[dim].get(code, code)
        rows.append(row)
    return pd.DataFrame(rows)
