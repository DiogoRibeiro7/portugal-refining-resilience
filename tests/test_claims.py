"""Tests for report-claim verification.

Each test reproduces a defect that reached a finished draft and was found by a human
reviewer rather than by the pipeline.
"""

import pandas as pd
import pytest

from portugal_refining_resilience.claims import (
    check_event_interval,
    check_flagged_cells_have_sensitivity,
    check_prose_numbers,
    check_sensitivity_survival,
    check_stated_sample_sizes,
    parse_latex_tables,
    prose_without_tables,
    table_numbers,
    verify_table_values,
)

TABLE = r"""
\begin{table}[htbp]
\centering
\caption{Segmented monthly event model.}
\label{tab:monthly}
\begin{tabular}{llrr}
\toprule
Outcome & Term & Estimate & $p$ \\
\midrule
Refinery output & Matosinhos transition & $-106.00$ & 0.005 \\
Net imports / demand & Matosinhos transition & $+0.2171$ & 0.004 \\
\bottomrule
\end{tabular}
\end{table}
"""


def _models() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "term": ["matosinhos_transition", "matosinhos_transition"],
            "estimate": [-105.998935, 0.217107],
            "p_value": [0.005259, 0.003606],
            "n_obs": [240, 240],
        }
    )


def test_parse_latex_tables_attributes_rows_to_the_enclosing_label() -> None:
    """A label from an earlier float must not capture a later table's rows."""
    document = r"\section{X}\label{sec:x}" + TABLE

    tables = parse_latex_tables(document)

    assert set(tables) == {"tab:monthly"}
    assert len(tables["tab:monthly"]) == 3  # header plus two body rows


def test_table_numbers_reads_the_printed_values() -> None:
    rows = parse_latex_tables(TABLE)["tab:monthly"]

    values = table_numbers(rows)

    assert -106.0 in values
    assert 0.2171 in values


def test_verify_table_values_accepts_correctly_rounded_numbers() -> None:
    rows = parse_latex_tables(TABLE)["tab:monthly"]

    assert verify_table_values("tab:monthly", rows, [_models()]) == []


def test_verify_table_values_catches_a_stale_coefficient() -> None:
    """The published draft carried coefficients from a superseded model run."""
    stale = TABLE.replace("$-106.00$", "$-105.21$")
    rows = parse_latex_tables(stale)["tab:monthly"]

    unmatched = verify_table_values("tab:monthly", rows, [_models()])

    assert unmatched == [-105.21]


def test_verify_table_values_tolerates_half_a_printed_unit() -> None:
    """122.75 printed as 122.8 must match; re-rounding would depend on tie-breaking."""
    frame = pd.DataFrame({"estimate": [122.75]})
    rows = [r"gasoline & exports & 122.8 \\"]

    assert verify_table_values("t", rows, [frame]) == []


def test_verify_table_values_ignores_years() -> None:
    frame = pd.DataFrame({"value": [1.0]})
    rows = [r"2013 & 2022 & 1.0 \\"]

    assert verify_table_values("t", rows, [frame]) == []


def test_check_stated_sample_sizes_catches_a_window_mismatch() -> None:
    """The draft said n=293 after the model had been restricted to 240 months."""
    tex = r"a model on $n=293$ observations"

    passed, detail = check_stated_sample_sizes(tex, _models())

    assert passed is False
    assert "293" in detail


def test_check_stated_sample_sizes_accepts_any_fitted_model() -> None:
    tex = r"$n=240$ months and $n=19$ years"
    annual = pd.DataFrame({"nobs": [19]})

    passed, _ = check_stated_sample_sizes(tex, [_models(), annual])

    assert passed is True


def test_check_event_interval_catches_the_wrong_gap() -> None:
    """The draft said the two events fall fourteen months apart; they fall ten."""
    tex = "the two fall fourteen months apart"
    dates = {"matosinhos_closure_start": "2021-05-01", "energy_stress_start": "2022-03-01"}

    passed, detail = check_event_interval(tex, dates)

    assert passed is False
    assert "10 months apart" in detail


def test_check_event_interval_accepts_the_right_gap() -> None:
    tex = "the transition and the shock fall ten months apart"
    dates = {"matosinhos_closure_start": "2021-05-01", "energy_stress_start": "2022-03-01"}

    passed, _ = check_event_interval(tex, dates)

    assert passed is True


def _reconciliation() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "year": [2022, 2019],
            "product": ["diesel", "gasoline"],
            "flow": ["exports", "imports"],
            "reconciliation_status": ["review", "review"],
        }
    )


def test_flagged_cells_without_a_sensitivity_fail() -> None:
    """A disputed cell drove a headline statistic with no alternative computed."""
    covered = pd.DataFrame({"year": [2022], "product": ["diesel"]})

    passed, detail = check_flagged_cells_have_sensitivity(_reconciliation(), [covered])

    assert passed is False
    assert "gasoline" in detail


def test_flagged_cells_with_a_sensitivity_pass() -> None:
    covered = pd.DataFrame({"year": [2022, 2019], "product": ["diesel", "gasoline"]})

    passed, detail = check_flagged_cells_have_sensitivity(_reconciliation(), [covered])

    assert passed is True
    assert "2 disputed cell(s)" in detail


def test_sensitivity_survival_names_results_that_flip() -> None:
    """Gasoline 2022 exports loses significance when the trade source is swapped."""
    sensitivity = pd.DataFrame(
        {
            "product": ["gasoline", "gasoline", "diesel", "diesel"],
            "outcome": ["exports_kt", "exports_kt", "exports_kt", "exports_kt"],
            "trade_source": ["primary", "corroborated", "primary", "corroborated"],
            "p_value": [0.020, 0.146, 0.000, 0.001],
        }
    )

    passed, detail = check_sensitivity_survival(sensitivity)

    assert passed is True  # informational, never blocks
    assert "gasoline/exports_kt" in detail
    assert "diesel" not in detail.split(":")[-1]


@pytest.mark.parametrize("empty", [pd.DataFrame(), pd.DataFrame({"product": []})])
def test_sensitivity_survival_handles_absent_input(empty: pd.DataFrame) -> None:
    passed, _ = check_sensitivity_survival(empty)

    assert passed is True


PROSE = r"""
Diesel demand averaged $4{,}522$~kt against output of $4{,}348$~kt.

\begin{table}[htbp]
\label{tab:x}
\begin{tabular}{lr}
\toprule
a & 99.9 \
\bottomrule
\end{tabular}
\end{table}
"""


def _bundle() -> list[pd.DataFrame]:
    return [pd.DataFrame({"value": [4522.0, 4348.0]})]


def test_prose_numbers_accepts_values_present_in_the_bundle() -> None:
    passed, _ = check_prose_numbers(PROSE, _bundle())

    assert passed is True


def test_prose_numbers_catches_a_stale_value() -> None:
    """The claim matrix carried averages from a superseded window."""
    stale = PROSE.replace("$4{,}522$", "$5{,}064$")

    passed, detail = check_prose_numbers(stale, _bundle())

    assert passed is False
    assert "5064" in detail.replace(".0", "")


def test_prose_numbers_ignores_table_contents() -> None:
    """Table values are checked against their own declared source, not the whole bundle."""
    passed, _ = check_prose_numbers(PROSE, _bundle())

    assert passed is True  # 99.9 lives inside the table and is not checked here


def test_prose_numbers_honours_the_allow_list() -> None:
    derived = PROSE.replace("$4{,}348$~kt", "$0.6931$")

    assert check_prose_numbers(derived, _bundle())[0] is False
    assert check_prose_numbers(derived, _bundle(), allow={0.6931})[0] is True


def test_prose_without_tables_removes_float_environments() -> None:
    body = prose_without_tables(PROSE)

    assert "4{,}522" in body
    assert "99.9" not in body
