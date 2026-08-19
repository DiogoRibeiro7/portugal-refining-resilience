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
    """Justifying every row must not turn a broad disagreement into a pass."""
    path = tmp_path / "reconciliation.csv"
    frame = _reconciliation_frame({})
    frame["reconciliation_status"] = "review"
    frame.to_csv(path, index=False)
    everything = frame[["year", "product", "flow"]].to_dict("records")

    passed, detail = validate_reconciliation(path, accepted_divergences=everything)

    assert passed is False
    assert "without invoking an exception" in detail


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


def test_validate_monthly_event_outputs_requires_phase_trend_terms(tmp_path: Path) -> None:
    """A level term without its slope companion cannot be read as the whole effect."""
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
    terms = ["matosinhos_transition", "energy_stress_2022", "post_stress"]
    pd.DataFrame(
        {
            "product": ["diesel"] * len(terms),
            "outcome": ["imports_kt"] * len(terms),
            "term": terms,
            "estimate": [1.0] * len(terms),
            "std_error": [0.1] * len(terms),
            "p_value": [0.05] * len(terms),
            "n_obs": [48] * len(terms),
        }
    ).to_csv(tmp_path / "monthly_event_models.csv", index=False)

    passed, detail = validate_monthly_event_outputs(tmp_path)

    assert passed is False
    assert "matosinhos_transition_trend" in detail


def test_validate_monthly_event_outputs_accepts_level_and_slope_terms(tmp_path: Path) -> None:
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
    phases = ["matosinhos_transition", "energy_stress_2022", "post_stress"]
    terms = phases + [f"{phase}_trend" for phase in phases]
    pd.DataFrame(
        {
            "product": ["diesel"] * len(terms),
            "outcome": ["imports_kt"] * len(terms),
            "term": terms,
            "estimate": [1.0] * len(terms),
            "std_error": [0.1] * len(terms),
            "p_value": [0.05] * len(terms),
            "n_obs": [48] * len(terms),
        }
    ).to_csv(tmp_path / "monthly_event_models.csv", index=False)

    passed, detail = validate_monthly_event_outputs(tmp_path)

    assert passed is True
    assert "1 outcomes" in detail


def test_validate_price_outputs_requires_model_choice(tmp_path: Path) -> None:
    pd.DataFrame({"product": ["diesel"]}).to_csv(
        tmp_path / "price_stationarity_diagnostics.csv", index=False
    )

    passed, detail = validate_price_outputs(tmp_path)

    assert passed is False
    assert "price_model_choice.csv" in detail


def _reconciliation_frame(statuses: dict[tuple[int, str, str], str]) -> pd.DataFrame:
    rows = []
    for year in range(2019, 2025):
        for product in ("diesel", "gasoline"):
            for flow in ("imports", "exports"):
                rows.append(
                    {
                        "year": year,
                        "product": product,
                        "flow": flow,
                        "reconciliation_status": statuses.get(
                            (year, product, flow), "within_tolerance"
                        ),
                    }
                )
    return pd.DataFrame(rows)


def test_validate_reconciliation_rejects_an_unexplained_divergence(tmp_path: Path) -> None:
    path = tmp_path / "jodi_dgeg_trade_reconciliation.csv"
    _reconciliation_frame({(2022, "diesel", "exports"): "review"}).to_csv(path, index=False)

    passed, detail = validate_reconciliation(path)

    assert passed is False
    assert "unexplained divergence" in detail
    assert "2022" in detail


def test_validate_reconciliation_accepts_a_justified_divergence(tmp_path: Path) -> None:
    path = tmp_path / "jodi_dgeg_trade_reconciliation.csv"
    _reconciliation_frame({(2022, "diesel", "exports"): "review"}).to_csv(path, index=False)

    passed, detail = validate_reconciliation(
        path,
        accepted_divergences=[
            {"year": 2022, "product": "diesel", "flow": "exports", "note": "vintage"}
        ],
    )

    assert passed is True
    assert "1 justified divergence" in detail


def test_validate_reconciliation_still_fails_a_new_divergence(tmp_path: Path) -> None:
    """Justifying one cell must not licence the next vintage to drift."""
    path = tmp_path / "jodi_dgeg_trade_reconciliation.csv"
    _reconciliation_frame(
        {(2022, "diesel", "exports"): "review", (2023, "gasoline", "imports"): "review"}
    ).to_csv(path, index=False)

    passed, detail = validate_reconciliation(
        path,
        accepted_divergences=[{"year": 2022, "product": "diesel", "flow": "exports"}],
    )

    assert passed is False
    assert "2023" in detail


def test_validate_reconciliation_reports_entries_that_no_longer_diverge(tmp_path: Path) -> None:
    path = tmp_path / "jodi_dgeg_trade_reconciliation.csv"
    _reconciliation_frame({}).to_csv(path, index=False)

    passed, detail = validate_reconciliation(
        path,
        accepted_divergences=[{"year": 2022, "product": "diesel", "flow": "exports"}],
    )

    assert passed is True
    assert "no longer diverge" in detail
