from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from portugal_refining_resilience.prices import (
    choose_price_model,
    extract_weekly_prices,
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
