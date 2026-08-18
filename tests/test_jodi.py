import pandas as pd
import pytest

from portugal_refining_resilience.jodi import annualise, build_monthly_panel, filter_portugal_fuels


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


def test_build_monthly_panel_preserves_event_timing() -> None:
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(["2021-04-01", "2021-04-01", "2021-05-01", "2021-05-01"]),
            "product_canonical": ["diesel"] * 4,
            "flow_canonical": ["imports", "exports", "imports", "exports"],
            "value": [10.0, 3.0, 12.0, 2.0],
        }
    )

    out = build_monthly_panel(df)

    assert out.loc[0, "event_phase"] == "pre_matosinhos_closure"
    assert out.loc[1, "event_phase"] == "matosinhos_transition"
    assert out.loc[1, "net_imports_kt"] == pytest.approx(10.0)
