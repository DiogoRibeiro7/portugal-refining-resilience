from pathlib import Path

import pandas as pd

from portugal_refining_resilience.readiness import (
    validate_jodi_completeness,
    validate_monthly_event_outputs,
    validate_monthly_panel,
    validate_price_outputs,
    validate_reconciliation,
)


def test_validate_jodi_completeness_rejects_incomplete_rows(tmp_path: Path) -> None:
    path = tmp_path / "jodi_trade_annual_completeness.csv"
    pd.DataFrame({"year": [2020], "n_months": [11], "complete_year": [False]}).to_csv(
        path, index=False
    )

    passed, detail = validate_jodi_completeness([path], start_year=2020, end_year=2020)

    assert passed is False
    assert "incomplete" in detail


def test_validate_jodi_completeness_rejects_string_false(tmp_path: Path) -> None:
    path = tmp_path / "jodi_trade_annual_completeness.csv"
    pd.DataFrame({"year": [2020], "n_months": [12], "complete_year": ["False"]}).to_csv(
        path, index=False
    )

    passed, detail = validate_jodi_completeness([path], start_year=2020, end_year=2020)

    assert passed is False
    assert "False" in detail


def test_validate_reconciliation_requires_tolerance_share(tmp_path: Path) -> None:
    path = tmp_path / "reconciliation.csv"
    pd.DataFrame({"reconciliation_status": ["review"] * 20}).to_csv(path, index=False)

    passed, detail = validate_reconciliation(path)

    assert passed is False
    assert "within tolerance" in detail


def test_validate_monthly_panel_requires_all_event_phases(tmp_path: Path) -> None:
    path = tmp_path / "monthly.csv"
    pd.DataFrame(
        {
            "date": ["2021-04-01"],
            "product": ["diesel"],
            "event_phase": ["pre_matosinhos_closure"],
        }
    ).to_csv(path, index=False)

    passed, detail = validate_monthly_panel(path)

    assert passed is False
    assert "missing event phases" in detail


def test_validate_monthly_event_outputs_require_phase_terms(tmp_path: Path) -> None:
    pd.DataFrame(
        {
            "product": ["diesel"],
            "outcome": ["imports_kt"],
            "event_phase": ["pre_matosinhos_closure"],
            "n_months": [24],
            "mean_value": [100.0],
            "std_value": [5.0],
        }
    ).to_csv(tmp_path / "monthly_event_phase_summary.csv", index=False)
    pd.DataFrame(
        {
            "product": ["diesel"],
            "outcome": ["imports_kt"],
            "term": ["matosinhos_transition"],
            "estimate": [1.0],
            "std_error": [0.1],
            "p_value": [0.05],
            "n_obs": [48],
        }
    ).to_csv(tmp_path / "monthly_event_models.csv", index=False)

    passed, detail = validate_monthly_event_outputs(tmp_path)

    assert passed is False
    assert "missing phase terms" in detail


def test_validate_price_outputs_requires_model_choice(tmp_path: Path) -> None:
    pd.DataFrame({"product": ["diesel"]}).to_csv(
        tmp_path / "price_stationarity_diagnostics.csv", index=False
    )

    passed, detail = validate_price_outputs(tmp_path)

    assert passed is False
    assert "price_model_choice.csv" in detail
