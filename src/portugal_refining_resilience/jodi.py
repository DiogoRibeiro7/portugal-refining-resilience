from __future__ import annotations

import zipfile
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from .events import assign_monthly_event_phase
from .metrics import add_supply_metrics

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "country": ("country", "ref_area", "area", "country_name"),
    "product": ("product", "energy_product", "product_name"),
    "flow": ("flow", "flow_breakdown", "flow_name"),
    "unit": ("unit", "unit_measure", "unit_name"),
    "time": ("time", "time_period", "period", "month"),
    "value": ("value", "obs_value", "observation_value"),
    "assessment": ("assessment", "assessment_code", "colour_code", "color_code"),
}

_PRODUCT_CODES: dict[str, set[str]] = {
    "diesel": {"GASDIES", "GASDIESEL", "GAS_DIESEL"},
    "gasoline": {"GASOLINE", "MOGAS"},
}
_PRODUCT_LABEL_ALIASES: dict[str, set[str]] = {
    "diesel": {
        "AUTOMOTIVE GAS OIL",
        "DIESEL",
        "GAS OIL AND DIESEL OIL",
        "GAS/DIESEL OIL",
        "GASOLEO",
        "GASÓLEO",
    },
    "gasoline": {
        "EURO-SUPER 95",
        "EUROSUPER 95",
        "GASOLINA",
        "GASOLINE",
        "MOTOR GASOLINE",
        "MOTOR/AVIATION GASOLINE",
    },
}
# ``KTONS`` is the code the JODI world secondary CSV actually ships; the others are
# accepted so hand-built or re-exported extracts still resolve.
_TONNE_UNIT_CODES = {
    "KT",
    "KTON",
    "KTONS",
    "1000 TONNES",
    "1000 TONS",
    "THOUSAND TONNES",
    "THOUSAND TONS",
}


def _normalise_name(name: object) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def _normalise_code(value: object) -> str:
    return str(value).strip().upper().replace("\u00a0", " ")


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
    allow_label_fallback: bool = True,
) -> pd.DataFrame:
    """Select Portugal, gasoline/diesel, and tonne observations using audited aliases.

    Exact JODI codes are preferred. Human-readable labels are accepted only when
    they match the explicit alias lists above.
    """
    out = df.copy()
    for column in ("country", "product", "flow", "unit"):
        if column not in out.columns:
            raise ValueError(f"Missing canonical JODI column: {column}")
        out[f"_{column}"] = out[column].map(_normalise_code)

    country_ok = out["_country"].isin({"PT", "PORTUGAL"})
    diesel_ok = out["_product"].isin(_PRODUCT_CODES["diesel"])
    gasoline_ok = out["_product"].isin(_PRODUCT_CODES["gasoline"])
    if allow_label_fallback:
        diesel_ok |= out["_product"].isin(_PRODUCT_LABEL_ALIASES["diesel"])
        gasoline_ok |= out["_product"].isin(_PRODUCT_LABEL_ALIASES["gasoline"])
    tonne_ok = out["_unit"].isin(_TONNE_UNIT_CODES)

    # JODI CSVs use short flow codes (for example TOTEXPSB) while some exports
    # expose human-readable labels. Support both explicitly.
    flow_aliases: dict[str, set[str]] = {
        "exports": {"EXPORT", "EXPORTS", "TOTEXPSB"},
        "imports": {"IMPORT", "IMPORTS", "TOTIMPSB"},
        "refinery output": {"REFINERY OUTPUT", "REFGROUT"},
        "demand": {"DEMAND", "TOTDEMO"},
    }
    requested = {flow.strip().lower() for flow in flows}
    accepted_codes = set().union(
        *(flow_aliases[name] for name in requested if name in flow_aliases)
    )
    flow_mask = out["_flow"].isin(accepted_codes)
    for flow in requested:
        token = flow.upper().replace(" ", ".*")
        flow_mask |= out["_flow"].str.contains(token, regex=True)

    selected = out.loc[country_ok & (diesel_ok | gasoline_ok) & tonne_ok & flow_mask].copy()
    if selected.empty:
        # An empty selection means the source vocabulary moved, not that Portugal
        # reported nothing. Report which predicate eliminated everything rather than
        # handing back a silently empty panel.
        raise ValueError(
            "No JODI observations matched. Rows passing each filter: "
            f"country={int(country_ok.sum())}, "
            f"product={int((diesel_ok | gasoline_ok).sum())}, "
            f"unit={int(tonne_ok.sum())}, flow={int(flow_mask.sum())}. "
            f"Observed units={sorted(out['_unit'].unique())[:12]}, "
            f"products={sorted(out['_product'].unique())[:12]}, "
            f"flows={sorted(out['_flow'].unique())[:12]}."
        )
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
    require_complete_months: bool = True,
) -> pd.DataFrame:
    """Sum monthly physical quantities to annual fuel/flow totals.

    The output always includes completeness diagnostics. By default, annual
    values with fewer than 12 observed months are marked incomplete and their
    analytical ``value_kt`` is set to NaN.
    """
    required = {"year", "month", "product_canonical", "flow_canonical", value_column}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for annualisation: {sorted(missing)}")

    records: list[dict[str, object]] = []
    group_columns = ["year", "product_canonical", "flow_canonical"]
    for keys, group in df.groupby(group_columns, dropna=False):
        year, product, flow = keys
        year_int = int(cast("int | float | str", year))
        values = pd.to_numeric(group[value_column], errors="coerce")
        valid = group.loc[values.notna()].copy()
        months = sorted({int(month) for month in valid["month"].dropna()})
        duplicate_months = sorted(
            int(cast("int | float | str", month))
            for month, count in valid["month"].dropna().astype(int).value_counts().items()
            if count > 1
        )
        missing_months = [month for month in range(1, 13) if month not in months]
        complete_year = len(months) == 12 and not duplicate_months
        raw_total = float(values.sum(min_count=1)) if values.notna().any() else np.nan
        if "assessment" in group.columns:
            assessments = sorted(
                {str(value).strip() for value in group["assessment"].dropna() if str(value).strip()}
            )
            assessment_status = ";".join(assessments) if assessments else "not_available"
        else:
            assessment_status = "not_available"
        records.append(
            {
                "year": year_int,
                "product_canonical": str(product),
                "flow_canonical": str(flow),
                "value_kt": raw_total if complete_year or not require_complete_months else np.nan,
                "raw_month_sum_kt": raw_total,
                "n_months": len(months),
                "missing_months": ",".join(str(month) for month in missing_months),
                "duplicate_months": ",".join(str(month) for month in duplicate_months),
                "complete_year": complete_year,
                "assessment_status": assessment_status,
                "country": "PT",
                "source": "JODI",
            }
        )
    return pd.DataFrame(records)


def build_monthly_panel(df: pd.DataFrame, *, value_column: str = "value") -> pd.DataFrame:
    """Build a monthly product panel from canonical JODI fuel observations."""
    required = {"time", "product_canonical", "flow_canonical", value_column}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for monthly panel: {sorted(missing)}")
    frame = df.copy()
    frame["time"] = pd.to_datetime(frame["time"])
    frame["date"] = frame["time"].dt.to_period("M").dt.to_timestamp()
    frame["value_kt"] = pd.to_numeric(frame[value_column], errors="coerce")
    panel = (
        frame.pivot_table(
            index=["date", "product_canonical"],
            columns="flow_canonical",
            values="value_kt",
            aggfunc="sum",
        )
        .rename(
            columns={
                "imports": "imports_kt",
                "exports": "exports_kt",
                "demand": "demand_kt",
                "refinery output": "refinery_output_kt",
            }
        )
        .reset_index()
        .rename(columns={"product_canonical": "product"})
    )
    panel.columns.name = None
    panel["year"] = panel["date"].dt.year.astype(int)
    panel["month"] = panel["date"].dt.month.astype(int)
    panel["event_phase"] = assign_monthly_event_phase(panel["date"])
    if {"imports_kt", "exports_kt"}.issubset(panel.columns):
        panel["net_imports_kt"] = panel["imports_kt"] - panel["exports_kt"]
    if {"imports_kt", "exports_kt", "demand_kt"}.issubset(panel.columns):
        panel = add_supply_metrics(panel)
    return panel
