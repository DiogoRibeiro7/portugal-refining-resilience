import pandas as pd
import pytest

from portugal_refining_resilience.dgeg import canonicalise_trade_long, compare_trade_sources


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
