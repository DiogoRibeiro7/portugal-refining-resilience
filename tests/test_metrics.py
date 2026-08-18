import pandas as pd
import pytest

from portugal_refining_resilience.metrics import (
    add_supply_metrics,
    add_yoy,
    benchmark_deviation,
    safe_ratio,
)


def test_safe_ratio_zero_denominator_is_nan() -> None:
    out = safe_ratio(pd.Series([2.0, 1.0]), pd.Series([4.0, 0.0]))
    assert out.iloc[0] == pytest.approx(0.5)
    assert pd.isna(out.iloc[1])


def test_supply_metrics_identity() -> None:
    df = pd.DataFrame(
        {
            "imports_kt": [100.0],
            "exports_kt": [40.0],
            "demand_kt": [200.0],
            "refinery_output_kt": [120.0],
        }
    )
    out = add_supply_metrics(df)
    assert out.loc[0, "net_imports_kt"] == pytest.approx(60.0)
    assert out.loc[0, "gross_import_dependence"] == pytest.approx(0.5)
    assert out.loc[0, "net_import_to_demand_ratio"] == pytest.approx(0.3)
    assert out.loc[0, "refinery_output_to_demand_ratio"] == pytest.approx(0.6)
    assert "net_import_dependence" not in out.columns
    assert "domestic_output_coverage" not in out.columns


def test_add_yoy_skips_percent_for_signed_series() -> None:
    df = pd.DataFrame({"product": ["diesel", "diesel"], "year": [2021, 2022], "net": [-10, 10]})
    out = add_yoy(df, ["net"])
    assert out.loc[1, "net_yoy_change"] == pytest.approx(20)
    assert "net_yoy_pct" not in out.columns


def test_benchmark_deviation_reports_robust_statistics() -> None:
    df = pd.DataFrame(
        {
            "product": ["diesel"] * 5,
            "year": [2015, 2016, 2017, 2018, 2022],
            "value": [10.0, 11.0, 12.0, 13.0, 15.0],
        }
    )
    out = benchmark_deviation(
        df, value_column="value", target_year=2022, baseline_start=2015, baseline_end=2018
    )
    assert out.loc[0, "baseline_n"] == 4
    assert out.loc[0, "baseline_median"] == pytest.approx(11.5)
    assert out.loc[0, "robust_z_score"] > 0
