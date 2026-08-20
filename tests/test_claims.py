"""Tests for report-claim verification.

Each test reproduces a defect that reached a finished draft and was found by a human
reviewer rather than by the pipeline.
"""

import pandas as pd
import pytest

from portugal_refining_resilience.claims import (
    check_claim_matrix,
    check_event_interval,
    check_flagged_cells_have_sensitivity,
    check_prose_numbers,
    check_sensitivity_survival,
    check_stated_sample_sizes,
    claim_matrix_rows,
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


def test_prose_numbers_ignores_verified_table_contents() -> None:
    """Table values are checked against their own declared source, not the whole bundle."""
    passed, _ = check_prose_numbers(PROSE, _bundle(), checked_labels={"tab:x"})

    assert passed is True  # 99.9 lives in a table checked against its own source


def test_prose_numbers_still_checks_a_table_nothing_else_covers() -> None:
    """A table with no declared source used to be dropped here and checked nowhere.

    That is the hole the claim-evidence matrix fell through: an unmapped float was
    stripped from the prose and absent from the mapped tables, so its numbers were
    verified by neither pass.
    """
    unmapped = PROSE.replace("a & 99.9", "a & $99.9$")

    passed, detail = check_prose_numbers(unmapped, _bundle(), checked_labels=set())

    assert passed is False
    assert "99.9" in detail


def test_prose_numbers_sees_only_math_mode() -> None:
    """The prose pass reads math mode, which is why the matrix needs its own check.

    A bare ``99.9`` in running text is indistinguishable from a page or year number,
    so this pass cannot claim it. ``check_claim_matrix`` reads every number in a row
    instead, because there the surrounding table gives each one its meaning.
    """
    passed, _ = check_prose_numbers(PROSE, _bundle(), checked_labels=set())

    assert passed is True


def test_prose_numbers_honours_the_allow_list() -> None:
    derived = PROSE.replace("$4{,}348$~kt", "$0.6931$")

    assert check_prose_numbers(derived, _bundle())[0] is False
    assert check_prose_numbers(derived, _bundle(), allow={0.6931})[0] is True


def test_prose_without_tables_removes_only_verified_floats() -> None:
    body = prose_without_tables(PROSE, checked_labels={"tab:x"})

    assert "4{,}522" in body
    assert "99.9" not in body


def test_prose_without_tables_keeps_a_float_with_no_declared_source() -> None:
    body = prose_without_tables(PROSE, checked_labels=set())

    assert "99.9" in body


MATRIX = r"""
\begin{longtable}{llll}
\toprule
Claim & Where shown & Level & Caveat \\
\midrule
\endhead
Output shifts $-102.89$ kt/month & Table~\ref{tab:monthly} & association & Quote the trend \\
Diesel elasticity reaches $1.01$ & Table~\ref{tab:price} & association & Retail prices \\
Panel covers 2002--2024 & Section~\ref{sec:coverage} & descriptive & JODI starts late \\
\end{longtable}
"""


@pytest.fixture()
def matrix_sources() -> dict[str, list[pd.DataFrame]]:
    return {
        "tab:monthly": [pd.DataFrame({"estimate": [-102.888228, -148.246334]})],
        "tab:price": [pd.DataFrame({"estimate": [0.7348314, 1.0072139]})],
    }


def test_claim_matrix_rows_skips_the_header(matrix_sources: object) -> None:
    rows = claim_matrix_rows(MATRIX)

    assert len(rows) == 3
    assert all("Where shown" not in row for row in rows)


def test_claim_matrix_accepts_values_from_the_cited_table(
    matrix_sources: dict[str, list[pd.DataFrame]],
) -> None:
    passed, _ = check_claim_matrix(MATRIX, matrix_sources, [])

    assert passed is True


def test_claim_matrix_catches_a_stale_coefficient(
    matrix_sources: dict[str, list[pd.DataFrame]],
) -> None:
    """The matrix kept a coefficient from before the panel was extended."""
    stale = MATRIX.replace("$-102.89$", "$-106.00$")

    passed, detail = check_claim_matrix(stale, matrix_sources, [])

    assert passed is False
    assert "106" in detail


def test_claim_matrix_rejects_a_value_real_in_a_different_table(
    matrix_sources: dict[str, list[pd.DataFrame]],
) -> None:
    """Checking against the whole bundle would accept this; the cited source does not.

    ``0.7348`` is a genuine estimate, but it belongs to the price table rather than to
    the monthly one the row points at.
    """
    misplaced = MATRIX.replace("$-102.89$ kt/month", "$0.7348$ kt/month")

    passed, detail = check_claim_matrix(misplaced, matrix_sources, [])

    assert passed is False
    assert "0.7348" in detail


def test_claim_matrix_reads_a_year_range_as_years(
    matrix_sources: dict[str, list[pd.DataFrame]],
) -> None:
    """``2002--2024`` must not be parsed as the number -2024."""
    passed, _ = check_claim_matrix(MATRIX, matrix_sources, [])

    assert passed is True
