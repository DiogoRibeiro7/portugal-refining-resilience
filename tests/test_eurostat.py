import pandas as pd
import pytest
import requests
from dataexcept import DataLoadingError

from portugal_refining_resilience.eurostat import (
    build_balance_panel,
    canonicalise_oil_balance,
    fetch_jsonstat,
)


def test_eurostat_request_failure_retains_source_and_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cause = requests.ConnectionError("offline")

    def fail_get(*args: object, **kwargs: object) -> None:
        raise cause

    monkeypatch.setattr("portugal_refining_resilience.eurostat.requests.get", fail_get)
    with pytest.raises(DataLoadingError) as caught:
        fetch_jsonstat("nrg_cb_oil")

    assert caught.value.source.endswith("/nrg_cb_oil")
    assert caught.value.original is cause
    assert caught.value.__cause__ is cause


def test_canonicalise_oil_balance_selects_known_terms() -> None:
    raw = pd.DataFrame(
        {
            "geo": ["PT", "PT", "PT", "PT", "PT"],
            "time": [2022] * 5,
            "siec": ["x"] * 5,
            "siec_label": ["Gas oil and diesel oil"] * 5,
            "nrg_bal": ["a", "b", "c", "d", "ignored"],
            "nrg_bal_label": [
                "Imports",
                "Exports",
                "Gross inland deliveries - observed",
                "Refinery output",
                "Stock changes",
            ],
            "unit_label": ["Thousand tonnes"] * 5,
            "value": [100.0, 20.0, 90.0, 15.0, 1.0],
        }
    )

    out = canonicalise_oil_balance(raw)

    assert set(out["flow"]) == {"imports", "exports", "demand", "refinery_output"}
    assert set(out["product"]) == {"diesel"}


def test_build_balance_panel_calculates_ratios_and_residual() -> None:
    canonical = pd.DataFrame(
        {
            "year": [2022, 2022, 2022, 2022],
            "country": ["PT"] * 4,
            "product": ["diesel"] * 4,
            "flow": ["imports", "exports", "demand", "refinery_output"],
            "value_kt": [100.0, 20.0, 90.0, 15.0],
        }
    )

    out = build_balance_panel(canonical)

    assert out.loc[0, "net_import_to_demand_ratio"] == pytest.approx(80.0 / 90.0)
    assert out.loc[0, "refinery_output_to_demand_ratio"] == pytest.approx(15.0 / 90.0)
    assert out.loc[0, "balance_residual_kt"] == pytest.approx(5.0)
