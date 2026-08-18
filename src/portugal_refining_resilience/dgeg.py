from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .excel import normalise_text

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "year": ("year", "ano"),
    "product": ("product", "produto", "produto_petrolifero", "produto_petrolífero"),
    "flow": ("flow", "fluxo", "movement", "movimento"),
    "value": ("value", "valor", "quantity", "quantidade"),
    "unit": ("unit", "unidade", "unit_measure", "unidade_medida"),
}

_PRODUCT_ALIASES: dict[str, set[str]] = {
    "diesel": {
        "diesel",
        "gasoleo",
        "gasóleo",
        "gasoleo rodoviario",
        "gasóleo rodoviário",
        "gas oil and diesel oil",
    },
    "gasoline": {
        "gasolina",
        "gasoline",
        "motor gasoline",
        "gasolina auto",
        "gasolina sem chumbo",
    },
}

_FLOW_ALIASES: dict[str, set[str]] = {
    "imports": {"importacao", "importação", "importacoes", "importações", "imports"},
    "exports": {"exportacao", "exportação", "exportacoes", "exportações", "exports"},
}

_UNIT_TO_KT: dict[str, float] = {
    "kt": 1.0,
    "kton": 1.0,
    "mil toneladas": 1.0,
    "1000 t": 1.0,
    "t": 0.001,
    "ton": 0.001,
    "tonelada": 0.001,
    "toneladas": 0.001,
    "kg": 0.000001,
}


@dataclass(frozen=True)
class ReconciliationThresholds:
    """Default tolerances for source cross-check summaries."""

    warning_abs_kt: float = 25.0
    warning_pct: float = 5.0


def _normalise_column(name: object) -> str:
    return normalise_text(name).replace(" ", "_").replace("-", "_")


def _resolve_columns(columns: pd.Index) -> dict[str, str]:
    normalised = {_normalise_column(column): str(column) for column in columns}
    resolved: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if _normalise_column(alias) in normalised:
                resolved[canonical] = normalised[_normalise_column(alias)]
                break
    missing = sorted(set(_COLUMN_ALIASES) - set(resolved))
    if missing:
        raise ValueError(f"Could not resolve DGEG columns {missing}. Available: {list(columns)}")
    return resolved


def _map_alias(value: object, aliases: dict[str, set[str]], *, field: str) -> str | None:
    normalised = normalise_text(value)
    for canonical, accepted in aliases.items():
        if normalised in accepted:
            return canonical
    if normalised and normalised != "nan":
        raise ValueError(f"Unknown DGEG {field} label: {value!r}")
    return None


def _value_to_kt(value: object, unit: object) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return float("nan")
    unit_key = normalise_text(unit)
    if unit_key not in _UNIT_TO_KT:
        raise ValueError(f"Unknown DGEG unit: {unit!r}")
    return float(numeric) * _UNIT_TO_KT[unit_key]


#: Sheet names carrying annual product trade, matched without accents.
_TRADE_SHEET_FLOWS: dict[str, str] = {
    "importacoes": "importações",
    "exportacoes": "exportações",
}

#: Only the road-fuel columns are extracted. Matching is exact so that
#: ``gasolina de aviação`` and ``av. gas`` are never folded into motor gasoline.
_TRADE_PRODUCT_LABELS: dict[str, str] = {
    "gasolina": "gasolina",
    "gasoleo": "gasóleo",
}

_COUNTRY_HEADER = {"pais"}

#: Rows after the country block; everything from here down is footnote prose.
_FOOTNOTE_MARKERS = ("notas", "nota:", "os dados", "1 inclui", "2 inclui")


def _strip_accents(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(character for character in text if not unicodedata.combining(character))


def _fold(value: object) -> str:
    """Normalise a Portuguese spreadsheet label to accent-free lowercase."""
    return normalise_text(_strip_accents(value))


def read_trade_workbook(path: Path, *, year: int) -> pd.DataFrame:
    """Extract annual road-fuel trade from one DGEG import/export workbook.

    DGEG publishes one workbook per year laying out partner country by product in
    tonnes, with the product header on a row that also labels the country column.
    The header row is located rather than assumed, and unknown layouts raise, because
    a shifted column would silently reassign tonnage between fuels.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    workbook = pd.ExcelFile(path)
    records: list[dict[str, object]] = []
    for sheet in workbook.sheet_names:
        flow = _TRADE_SHEET_FLOWS.get(_fold(sheet))
        if flow is None:
            continue
        raw = pd.read_excel(path, sheet_name=sheet, header=None)
        header_rows = [
            index
            for index in range(len(raw))
            if raw.iloc[index].map(_fold).isin(_COUNTRY_HEADER).any()
        ]
        if not header_rows:
            raise ValueError(f"{path.name}:{sheet} has no country header row")
        header_row = header_rows[0]
        header = raw.iloc[header_row].map(_fold)

        for folded_label, source_label in _TRADE_PRODUCT_LABELS.items():
            positions = [position for position, value in enumerate(header) if value == folded_label]
            if len(positions) != 1:
                raise ValueError(
                    f"{path.name}:{sheet} expected exactly one {folded_label!r} column, "
                    f"found {len(positions)}. Header was: {list(header)}"
                )
            column = positions[0]
            body = raw.iloc[header_row + 1 :]
            labels = body.iloc[:, 0].map(_fold)
            values = pd.to_numeric(body.iloc[:, column], errors="coerce")

            # Only partner-country rows are summed. Every sheet also carries its own
            # total, which doubles the figure if included: newer workbooks leave the
            # label blank, older ones write "total geral". Footnote prose trails both.
            is_footnote = labels.str.startswith(_FOOTNOTE_MARKERS)
            is_blank = labels.eq("") | labels.eq("nan")
            is_total = labels.str.contains("total") | (is_blank & values.notna())
            is_country = ~is_blank & ~is_footnote & ~is_total
            total = values.loc[is_country].sum(min_count=1)

            # The sheet's own total is then a parse check rather than dead weight:
            # a mismatch means the product column block has moved.
            stated_totals = values.loc[is_total].dropna()
            stated_totals = stated_totals[stated_totals.ne(0)]
            if not stated_totals.empty and pd.notna(total) and total:
                stated = float(stated_totals.iloc[0])
                if abs(stated - float(total)) > 0.01 * abs(float(total)):
                    raise ValueError(
                        f"{path.name}:{sheet} {folded_label!r} country rows sum to {total:,.0f} "
                        f"but the sheet's own total states {stated:,.0f}. "
                        "The product column block has probably shifted."
                    )
            records.append(
                {
                    "year": year,
                    "product": source_label,
                    "flow": flow,
                    "value": float(total),
                    "unit": "toneladas",
                }
            )
    if not records:
        raise ValueError(
            f"{path.name} contained no import/export sheet. Sheets: {workbook.sheet_names}"
        )
    return pd.DataFrame(records)


def canonicalise_trade_long(df: pd.DataFrame, *, source: str = "DGEG") -> pd.DataFrame:
    """Canonicalise an audited long DGEG trade table to annual product flows.

    This expects the source-specific workbook extraction to have already produced
    a long table with year, product, flow, value and unit columns. Ambiguous labels
    are rejected so workbook-layout changes cannot pass silently.
    """
    columns = _resolve_columns(df.columns)
    out = df.rename(columns={source_name: target for target, source_name in columns.items()})
    out = out[["year", "product", "flow", "value", "unit"]].copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["product"] = out["product"].map(
        lambda value: _map_alias(value, _PRODUCT_ALIASES, field="product")
    )
    out["flow"] = out["flow"].map(lambda value: _map_alias(value, _FLOW_ALIASES, field="flow"))
    out["value_kt"] = [
        _value_to_kt(value, unit) for value, unit in zip(out["value"], out["unit"], strict=True)
    ]
    out = out.dropna(subset=["year", "product", "flow", "value_kt"]).copy()
    out["year"] = out["year"].astype(int)
    out["country"] = "PT"
    out["source"] = source
    grouped = out.groupby(["year", "country", "product", "flow", "source"], as_index=False).agg(
        value_kt=("value_kt", "sum")
    )
    return grouped


def compare_trade_sources(
    primary: pd.DataFrame,
    comparison: pd.DataFrame,
    *,
    primary_name: str = "JODI",
    comparison_name: str = "DGEG",
    thresholds: ReconciliationThresholds | None = None,
) -> pd.DataFrame:
    """Compare annual canonical trade tables and flag material source differences."""
    thresholds = thresholds or ReconciliationThresholds()
    required = {"year", "product", "flow", "value_kt"}
    for name, frame in {primary_name: primary, comparison_name: comparison}.items():
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{name} trade table missing columns: {sorted(missing)}")

    joined = primary.merge(
        comparison,
        on=["year", "product", "flow"],
        how="inner",
        suffixes=(f"_{primary_name.lower()}", f"_{comparison_name.lower()}"),
    )
    primary_value = joined[f"value_kt_{primary_name.lower()}"]
    comparison_value = joined[f"value_kt_{comparison_name.lower()}"]
    joined["difference_kt"] = primary_value - comparison_value
    joined["difference_pct_comparison"] = (
        100 * joined["difference_kt"] / comparison_value.replace(0, np.nan)
    )
    joined["reconciliation_status"] = np.where(
        (joined["difference_kt"].abs() > thresholds.warning_abs_kt)
        | (joined["difference_pct_comparison"].abs() > thresholds.warning_pct),
        "review",
        "within_tolerance",
    )
    return joined
