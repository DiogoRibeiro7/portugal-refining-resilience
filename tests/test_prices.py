from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from portugal_refining_resilience.prices import (
    choose_price_model,
    extract_weekly_prices,
    fit_error_correction_model,
    price_comovement_design,
    spread_stationarity,
    stationarity_diagnostics,
)


def test_price_comovement_design_adds_interaction_and_differences() -> None:
    dates = pd.date_range("2021-04-25", periods=4, freq="W")
    prices = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "country": ["PT"] * 4 + ["ES"] * 4,
            "product": ["diesel"] * 8,
            "price_without_tax_eur_per_1000l": [101, 102, 103, 104, 100, 100, 110, 110],
        }
    )

    out = price_comovement_design(prices, product="diesel", cutoff="2021-05-02")

    assert out.loc[0, "post"] == 0
    assert out.loc[1, "post"] == 1
    assert out.loc[1, "ES_x_post"] == out.loc[1, "ES"]
    assert np.isfinite(out.loc[1, "diff_log_PT"])


def test_stationarity_diagnostics_handles_short_series() -> None:
    frame = pd.DataFrame({"product": ["diesel"] * 3, "value": [1.0, 2.0, 3.0]})

    out = stationarity_diagnostics(
        frame, value_column="value", group_columns=["product"], min_observations=10
    )

    assert out.loc[0, "status"] == "insufficient_observations"
    assert bool(out.loc[0, "stationary_5pct"]) is False


def test_spread_stationarity_handles_short_design() -> None:
    design = pd.DataFrame({"PT": [1.0, 2.0], "ES": [1.0, 1.5]})

    out = spread_stationarity(design)

    assert out["status"] == "insufficient_observations"


def test_choose_price_model_handles_short_design() -> None:
    design = pd.DataFrame({"PT": [1.0, 2.0], "ES": [1.0, 1.5]})

    out = choose_price_model(design, product="diesel")

    assert out["model_family"] == "insufficient_observations"
    assert out["n_obs"] == 2


def _write_bulletin(
    path: Path, *, unit: str = "1000 l", countries: tuple[str, ...] = ("PT", "ES")
) -> Path:
    """Build a miniature Weekly Oil Bulletin workbook with the real layout."""
    dates = pd.date_range("2021-04-05", periods=4, freq="7D")
    sheets = {"wo": "Prices wo taxes", "with": "Prices with taxes"}
    with pd.ExcelWriter(path) as writer:
        for basis, sheet in sheets.items():
            headers: list[object] = ["Consumer prices"]
            units: list[object] = ["Date"]
            columns: list[list[object]] = [list(dates)]
            for country in countries:
                for token in ("euro95", "diesel"):
                    headers.append(f"{country}_price_{basis}_tax_{token}")
                    units.append(unit)
                    base = 1000.0 if basis == "wo" else 1600.0
                    columns.append([base + i for i in range(len(dates))])
            frame = pd.DataFrame(
                [
                    headers,
                    [None] * len(headers),
                    units,
                    *[list(row) for row in zip(*columns, strict=True)],
                ]
            )
            frame.to_excel(writer, sheet_name=sheet, header=False, index=False)
    return path


def test_extract_weekly_prices_returns_the_tidy_contract(tmp_path: Path) -> None:
    workbook = _write_bulletin(tmp_path / "bulletin.xlsx")

    tidy = extract_weekly_prices(workbook)

    assert list(tidy.columns) == [
        "date",
        "country",
        "product",
        "price_with_tax_eur_per_1000l",
        "price_without_tax_eur_per_1000l",
    ]
    assert set(tidy["country"]) == {"PT", "ES"}
    assert set(tidy["product"]) == {"diesel", "gasoline"}
    assert not tidy.duplicated(["date", "country", "product"]).any()
    assert tidy["price_without_tax_eur_per_1000l"].notna().all()


def test_extract_weekly_prices_rejects_an_unexpected_unit(tmp_path: Path) -> None:
    """A silently rebadged unit would feed the price models directly."""
    workbook = _write_bulletin(tmp_path / "bulletin.xlsx", unit="litre")

    with pytest.raises(ValueError, match="expected '1000 l'"):
        extract_weekly_prices(workbook)


def test_extract_weekly_prices_rejects_a_missing_country(tmp_path: Path) -> None:
    workbook = _write_bulletin(tmp_path / "bulletin.xlsx", countries=("PT",))

    with pytest.raises(ValueError, match="missing price columns"):
        extract_weekly_prices(workbook)


def _cointegrated_design(
    *, beta: float = 0.9, gamma: float = -0.25, theta: float = 0.6, n: int = 600
) -> pd.DataFrame:
    """A PT series that error-corrects toward a known long-run relation with ES."""
    rng = np.random.default_rng(7)
    log_es = np.cumsum(rng.normal(0, 0.02, n)) + np.log(1000.0)
    alpha = 0.5
    log_pt = np.empty(n)
    log_pt[0] = alpha + beta * log_es[0]
    for t in range(1, n):
        gap = log_pt[t - 1] - (alpha + beta * log_es[t - 1])
        log_pt[t] = (
            log_pt[t - 1] + gamma * gap + theta * (log_es[t] - log_es[t - 1]) + rng.normal(0, 0.004)
        )
    frame = pd.DataFrame({"date": pd.date_range("2015-01-04", periods=n, freq="7D")})
    frame["log_ES"] = log_es
    frame["log_PT"] = log_pt
    frame["diff_log_ES"] = frame["log_ES"].diff()
    frame["diff_log_PT"] = frame["log_PT"].diff()
    frame["post"] = (frame["date"] >= "2021-05-01").astype(int)
    return frame


def test_error_correction_model_recovers_the_cointegrating_vector() -> None:
    result = fit_error_correction_model(_cointegrated_design(beta=0.9))

    assert result["cointegrating_slope"] == pytest.approx(0.9, abs=0.03)


def test_error_correction_model_recovers_adjustment_and_pass_through() -> None:
    result = fit_error_correction_model(_cointegrated_design(gamma=-0.25, theta=0.6))
    model = result["model"]

    assert model.params["disequilibrium_lag"] == pytest.approx(-0.25, abs=0.06)
    assert model.params["disequilibrium_lag"] < 0  # a gap above the relation is pulled back
    assert model.pvalues["disequilibrium_lag"] < 0.01
    assert model.params["diff_log_ES"] == pytest.approx(0.6, abs=0.05)


def test_error_correction_model_finds_no_regime_change_when_there_is_none() -> None:
    """Both interactions must be flat when the process is stable across the cutoff."""
    result = fit_error_correction_model(_cointegrated_design())
    model = result["model"]

    assert model.pvalues["disequilibrium_lag_x_post"] > 0.05
    assert model.pvalues["diff_log_ES_x_post"] > 0.05


def test_error_correction_model_requires_the_design_columns() -> None:
    frame = pd.DataFrame({"log_PT": [1.0] * 30, "log_ES": [1.0] * 30})

    with pytest.raises(ValueError, match="Price design missing columns"):
        fit_error_correction_model(frame)


def test_error_correction_model_requires_enough_levels() -> None:
    frame = _cointegrated_design(n=600).head(15)

    with pytest.raises(ValueError, match="at least 20 paired price levels"):
        fit_error_correction_model(frame)
