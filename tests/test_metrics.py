import pandas as pd
import pytest

from portugal_refining_resilience.metrics import add_supply_metrics, safe_ratio


def test_safe_ratio_zero_denominator_is_nan() -> None:
    out = safe_ratio(pd.Series([2.0, 1.0]), pd.Series([4.0, 0.0]))
    assert out.iloc[0] == pytest.approx(0.5)
    assert pd.isna(out.iloc[1])


def test_supply_metrics_identity() -> None:
    df = pd.DataFrame({"imports_kt": [100.0], "exports_kt": [40.0], "demand_kt": [200.0]})
    out = add_supply_metrics(df)
    assert out.loc[0, "net_imports_kt"] == pytest.approx(60.0)
    assert out.loc[0, "gross_import_dependence"] == pytest.approx(0.5)
    assert out.loc[0, "net_import_dependence"] == pytest.approx(0.3)
