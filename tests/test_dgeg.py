from pathlib import Path

import pandas as pd
import pytest

from portugal_refining_resilience.dgeg import (
    canonicalise_trade_long,
    compare_trade_sources,
    read_sales_workbook,
    read_trade_workbook,
)


def test_canonicalise_trade_long_maps_portuguese_labels_to_kt() -> None:
    raw = pd.DataFrame(
        {
            "Ano": [2022, 2022],
            "Produto": ["Gasóleo", "Gasolina"],
            "Movimento": ["Importações", "Exportações"],
            "Quantidade": [2500.0, 750.0],
            "Unidade": ["toneladas", "toneladas"],
        }
    )

    out = canonicalise_trade_long(raw)

    assert out.loc[0, "product"] == "diesel"
    assert out.loc[0, "flow"] == "imports"
    assert out.loc[0, "value_kt"] == pytest.approx(2.5)
    assert set(out["source"]) == {"DGEG"}


def test_canonicalise_trade_long_rejects_unknown_product() -> None:
    raw = pd.DataFrame(
        {
            "year": [2022],
            "product": ["jet fuel"],
            "flow": ["imports"],
            "value": [1.0],
            "unit": ["kt"],
        }
    )

    with pytest.raises(ValueError, match="Unknown DGEG product"):
        canonicalise_trade_long(raw)


def test_compare_trade_sources_flags_large_differences() -> None:
    primary = pd.DataFrame(
        {"year": [2022], "product": ["diesel"], "flow": ["imports"], "value_kt": [200.0]}
    )
    comparison = pd.DataFrame(
        {"year": [2022], "product": ["diesel"], "flow": ["imports"], "value_kt": [100.0]}
    )

    out = compare_trade_sources(primary, comparison)

    assert out.loc[0, "difference_kt"] == pytest.approx(100.0)
    assert out.loc[0, "difference_pct_comparison"] == pytest.approx(100.0)
    assert out.loc[0, "reconciliation_status"] == "review"


def test_compare_trade_sources_tolerates_a_small_absolute_difference() -> None:
    """A big percentage on a small series is not material when the tonnage is not."""
    primary = pd.DataFrame(
        {"year": [2022], "product": ["diesel"], "flow": ["imports"], "value_kt": [120.0]}
    )
    comparison = pd.DataFrame(
        {"year": [2022], "product": ["diesel"], "flow": ["imports"], "value_kt": [100.0]}
    )

    out = compare_trade_sources(primary, comparison)

    assert out.loc[0, "difference_pct_comparison"] == pytest.approx(20.0)
    assert out.loc[0, "reconciliation_status"] == "within_tolerance"


def _write_dgeg_workbook(path: Path, *, total_label: str | None) -> Path:
    """Build a miniature DGEG workbook: countries, then the sheet's own total row.

    ``total_label`` is ``None`` for the blank-labelled total used by the newer
    workbooks and ``"Total Geral"`` for the older ones.
    """
    header = ["País", "GPL", "Gasolina", "Gasolina de aviação", "Jets", "Gasóleo"]
    countries = [
        ["Espanha", 10.0, 100.0, 5.0, 7.0, 400.0],
        ["Paises Baixos", 20.0, 200.0, 6.0, 8.0, 600.0],
    ]
    total_row = [total_label, 30.0, 300.0, 11.0, 15.0, 1000.0]
    blank: list[object] = [None] * len(header)
    with pd.ExcelWriter(path) as writer:
        for sheet in ("Importações", "Exportações"):
            rows = [
                blank,
                blank,
                blank,
                blank,
                blank,
                blank,
                header,
                *countries,
                total_row,
                ["Notas:", None, None, None, None, None],
            ]
            pd.DataFrame(rows).to_excel(writer, sheet_name=sheet, header=False, index=False)
    return path


@pytest.mark.parametrize("total_label", [None, "Total Geral"])
def test_read_trade_workbook_excludes_the_sheets_own_total(
    tmp_path: Path, total_label: str | None
) -> None:
    """Including the total row silently doubled every DGEG figure."""
    workbook = _write_dgeg_workbook(tmp_path / "dgeg.xlsx", total_label=total_label)

    out = read_trade_workbook(workbook, year=2023)

    diesel_imports = out.loc[out["product"].eq("gasóleo") & out["flow"].eq("importações"), "value"]
    assert float(diesel_imports.iloc[0]) == pytest.approx(1000.0)
    gasoline_imports = out.loc[
        out["product"].eq("gasolina") & out["flow"].eq("importações"), "value"
    ]
    assert float(gasoline_imports.iloc[0]) == pytest.approx(300.0)


def test_read_trade_workbook_never_folds_aviation_into_motor_gasoline(tmp_path: Path) -> None:
    workbook = _write_dgeg_workbook(tmp_path / "dgeg.xlsx", total_label=None)

    out = read_trade_workbook(workbook, year=2023)

    gasoline = out.loc[out["product"].eq("gasolina") & out["flow"].eq("exportações"), "value"]
    assert float(gasoline.iloc[0]) == pytest.approx(300.0)  # not 300 + 11 aviation


def test_read_trade_workbook_rejects_a_shifted_column_block(tmp_path: Path) -> None:
    """The sheet's own total is used as a parse check, not ignored."""
    path = tmp_path / "dgeg.xlsx"
    header = ["País", "Gasolina", "Gasóleo"]
    blank: list[object] = [None] * len(header)
    rows = [blank] * 6 + [header, ["Espanha", 100.0, 400.0], [None, 100.0, 999.0]]
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Importações", header=False, index=False)

    with pytest.raises(ValueError, match="probably shifted"):
        read_trade_workbook(path, year=2023)


def test_reconciliation_does_not_flag_a_large_series_on_the_absolute_floor() -> None:
    """25 kt against a 1600 kt series is 1.6%, not the 5% the percentage limit states."""
    primary = pd.DataFrame(
        {"year": [2023], "product": ["diesel"], "flow": ["imports"], "value_kt": [1597.0]}
    )
    comparison = pd.DataFrame(
        {"year": [2023], "product": ["diesel"], "flow": ["imports"], "value_kt": [1631.6]}
    )

    out = compare_trade_sources(primary, comparison, primary_name="JODI", comparison_name="DGEG")

    assert abs(float(out.loc[0, "difference_kt"])) > 25.0
    assert abs(float(out.loc[0, "difference_pct_comparison"])) < 5.0
    assert out.loc[0, "reconciliation_status"] == "within_tolerance"


def test_reconciliation_flags_a_row_breaching_both_limits() -> None:
    primary = pd.DataFrame(
        {"year": [2022], "product": ["diesel"], "flow": ["exports"], "value_kt": [331.0]}
    )
    comparison = pd.DataFrame(
        {"year": [2022], "product": ["diesel"], "flow": ["exports"], "value_kt": [622.2]}
    )

    out = compare_trade_sources(primary, comparison, primary_name="JODI", comparison_name="DGEG")

    assert out.loc[0, "reconciliation_status"] == "review"


def _write_sales_workbook(path: Path) -> Path:
    """DGEG long sales layout: products down, years across, sections stacked."""
    rows: list[list[object]] = [[None] * 4 for _ in range(7)]
    rows.append(["Mercado Interno", 2023, "2024p", None])
    rows.append(["GPL", 100_000, 110_000, None])
    rows.append(["Gas. auto", 43_000, 56_000, None])
    rows.append(["Gasolinas", 1_194_000, 1_269_000, None])
    rows.append(["Gasóleo", 4_658_000, 4_538_000, None])
    rows.append(["Gasóleo colorido e marcado", 326_000, 331_000, None])
    rows.append(["Mercado de bancas marítimas", None, None, None])
    rows.append(["Gasóleo", 9_000_000, 9_000_000, None])  # must never be counted
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="DGEG", header=False, index=False)
    return path


def test_read_sales_workbook_sums_the_diesel_components(tmp_path: Path) -> None:
    """Road gasoil alone runs ~10% below the JODI and Eurostat demand concept."""
    out = read_sales_workbook(_write_sales_workbook(tmp_path / "sales.xlsx"))

    diesel = out.loc[out["product"].eq("diesel") & out["year"].eq(2024), "demand_kt"]
    assert float(diesel.iloc[0]) == pytest.approx(4538.0 + 331.0)


def test_read_sales_workbook_uses_gasolinas_not_the_gas_auto_subline(tmp_path: Path) -> None:
    out = read_sales_workbook(_write_sales_workbook(tmp_path / "sales.xlsx"))

    gasoline = out.loc[out["product"].eq("gasoline") & out["year"].eq(2024), "demand_kt"]
    assert float(gasoline.iloc[0]) == pytest.approx(1269.0)


def test_read_sales_workbook_excludes_bunker_sales(tmp_path: Path) -> None:
    """Marine bunker gasoil sits in a later section and is not domestic demand."""
    out = read_sales_workbook(_write_sales_workbook(tmp_path / "sales.xlsx"))

    assert float(out["demand_kt"].max()) < 9000.0


def test_read_sales_workbook_rejects_a_missing_component_row(tmp_path: Path) -> None:
    path = tmp_path / "sales.xlsx"
    rows: list[list[object]] = [[None] * 3 for _ in range(7)]
    rows.append(["Mercado Interno", 2023, "2024p"])
    rows.append(["Gasolinas", 1_194_000, 1_269_000])
    rows.append(["Gasóleo", 4_658_000, 4_538_000])
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="DGEG", header=False, index=False)

    with pytest.raises(ValueError, match="missing sales rows"):
        read_sales_workbook(path)
