import pandas as pd
import pytest

from portugal_refining_resilience.jodi import annualise, filter_portugal_fuels


def _monthly_frame(months: range) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "year": [2020] * len(months),
            "month": list(months),
            "product_canonical": ["diesel"] * len(months),
            "flow_canonical": ["imports"] * len(months),
            "value": [1.0] * len(months),
            "assessment": ["official"] * len(months),
        }
    )


def test_filter_portugal_fuels_prefers_exact_codes() -> None:
    df = pd.DataFrame(
        {
            "country": ["PT", "PT", "PT"],
            "product": ["GASDIES", "BIODIESEL BLEND", "GASOLINE"],
            "flow": ["TOTIMPSB", "TOTIMPSB", "TOTEXPSB"],
            "unit": ["KTON", "KTON", "PACKETS"],
            "time": pd.to_datetime(["2020-01-01"] * 3),
            "value": [1.0, 2.0, 3.0],
        }
    )
    out = filter_portugal_fuels(df)
    assert out["product_canonical"].tolist() == ["diesel"]
    assert out["flow_canonical"].tolist() == ["imports"]


def test_annualise_marks_incomplete_year_without_analytical_value() -> None:
    out = annualise(_monthly_frame(range(1, 12)))
    assert out.loc[0, "n_months"] == 11
    assert out.loc[0, "missing_months"] == "12"
    assert bool(out.loc[0, "complete_year"]) is False
    assert pd.isna(out.loc[0, "value_kt"])
    assert out.loc[0, "raw_month_sum_kt"] == pytest.approx(11.0)


def test_annualise_keeps_complete_year_value() -> None:
    out = annualise(_monthly_frame(range(1, 13)))
    assert bool(out.loc[0, "complete_year"]) is True
    assert out.loc[0, "value_kt"] == pytest.approx(12.0)
