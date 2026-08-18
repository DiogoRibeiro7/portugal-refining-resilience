from pathlib import Path

import pandas as pd
import pytest

from portugal_refining_resilience.dgeg import (
    canonicalise_trade_long,
    compare_trade_sources,
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
        {"year": [2022], "product": ["diesel"], "flow": ["imports"], "value_kt": [125.0]}
    )
    comparison = pd.DataFrame(
        {"year": [2022], "product": ["diesel"], "flow": ["imports"], "value_kt": [100.0]}
    )

    out = compare_trade_sources(primary, comparison)

    assert out.loc[0, "difference_kt"] == pytest.approx(25.0)
    assert out.loc[0, "difference_pct_comparison"] == pytest.approx(25.0)
    assert out.loc[0, "reconciliation_status"] == "review"


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
