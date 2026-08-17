from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd


_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "country": ("country", "ref_area", "area", "country_name"),
    "product": ("product", "energy_product", "product_name"),
    "flow": ("flow", "flow_breakdown", "flow_name"),
    "unit": ("unit", "unit_measure", "unit_name"),
    "time": ("time", "time_period", "period", "month"),
    "value": ("value", "obs_value", "observation_value"),
    "assessment": ("assessment", "assessment_code", "colour_code", "color_code"),
}


def _normalise_name(name: object) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def _resolve_columns(columns: pd.Index) -> dict[str, str]:
    normalised = {_normalise_name(column): str(column) for column in columns}
    resolved: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalised:
                resolved[canonical] = normalised[alias]
                break
    required = {"country", "product", "flow", "unit", "time", "value"}
    missing = sorted(required - resolved.keys())
    if missing:
        raise ValueError(
            f"Could not resolve JODI columns {missing}. Available columns: {list(columns)}"
        )
    return resolved


def read_secondary_zip(path: Path) -> pd.DataFrame:
    """Read the CSV payload from the JODI secondary-products ZIP."""
    if not path.exists():
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("No CSV found in JODI ZIP")
        with archive.open(csv_names[0]) as handle:
            return pd.read_csv(handle, low_memory=False)


def canonicalise_secondary(df: pd.DataFrame) -> pd.DataFrame:
    """Map common JODI long-format column names into a canonical schema."""
    columns = _resolve_columns(df.columns)
    rename = {source: target for target, source in columns.items()}
    out = df.rename(columns=rename).copy()
    keep = ["country", "product", "flow", "unit", "time", "value"]
    if "assessment" in out.columns:
        keep.append("assessment")
    out = out[keep]
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out["time"] = pd.to_datetime(out["time"].astype(str), errors="coerce")
    return out.dropna(subset=["time", "value"])


def filter_portugal_fuels(
    df: pd.DataFrame,
    *,
    flows: tuple[str, ...] = ("exports", "imports", "refinery output", "demand"),
) -> pd.DataFrame:
    """Select Portugal, gasoline/diesel, and tonne observations using label/code aliases."""
    out = df.copy()
    for column in ("country", "product", "flow", "unit"):
        if column not in out.columns:
            raise ValueError(f"Missing canonical JODI column: {column}")
        out[f"_{column}"] = out[column].astype(str).str.strip().str.upper()

    country_ok = out["_country"].isin({"PT", "PORTUGAL"})
    diesel_ok = out["_product"].str.contains("DIESEL|GAS/DIESEL|GAS OIL|GASDIES", regex=True)
    gasoline_ok = out["_product"].str.contains("GASOLINE|MOGAS", regex=True)
    tonne_ok = out["_unit"].str.contains("KTON|THOUSAND.*TON|1000.*TON|KT", regex=True)

    # JODI CSVs use short flow codes (for example TOTEXPSB) while some exports
    # expose human-readable labels. Support both explicitly.
    flow_aliases: dict[str, set[str]] = {
        "exports": {"EXPORT", "EXPORTS", "TOTEXPSB"},
        "imports": {"IMPORT", "IMPORTS", "TOTIMPSB"},
        "refinery output": {"REFINERY OUTPUT", "REFGROUT"},
        "demand": {"DEMAND", "TOTDEMO"},
    }
    requested = {flow.strip().lower() for flow in flows}
    accepted_codes = set().union(*(flow_aliases[name] for name in requested if name in flow_aliases))
    flow_mask = out["_flow"].isin(accepted_codes)
    for flow in requested:
        token = flow.upper().replace(" ", ".*")
        flow_mask |= out["_flow"].str.contains(token, regex=True)

    selected = out.loc[country_ok & (diesel_ok | gasoline_ok) & tonne_ok & flow_mask].copy()
    selected["product_canonical"] = "gasoline"
    selected.loc[diesel_ok.loc[selected.index], "product_canonical"] = "diesel"

    canonical_flow = pd.Series(index=selected.index, dtype="object")
    selected_flow_upper = selected["flow"].astype(str).str.strip().str.upper()
    for canonical_name, aliases in flow_aliases.items():
        mask = selected_flow_upper.isin(aliases) | selected_flow_upper.str.contains(
            canonical_name.upper().replace(" ", ".*"), regex=True
        )
        canonical_flow.loc[mask] = canonical_name
    selected["flow_canonical"] = canonical_flow
    selected = selected.dropna(subset=["flow_canonical"])
    selected["year"] = selected["time"].dt.year.astype(int)
    selected["month"] = selected["time"].dt.month.astype(int)
    return selected.drop(columns=[c for c in selected.columns if c.startswith("_")])


def annualise(
    df: pd.DataFrame,
    *,
    value_column: str = "value",
) -> pd.DataFrame:
    """Sum monthly physical quantities to annual fuel/flow totals."""
    required = {"year", "product_canonical", "flow_canonical", value_column}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for annualisation: {sorted(missing)}")
    grouped = (
        df.groupby(["year", "product_canonical", "flow_canonical"], as_index=False)[value_column]
        .sum(min_count=1)
        .rename(columns={value_column: "value_kt"})
    )
    grouped["country"] = "PT"
    grouped["source"] = "JODI"
    return grouped
