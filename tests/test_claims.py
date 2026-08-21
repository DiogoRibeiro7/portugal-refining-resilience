"""Tests for report-claim verification.

Each test reproduces a failure mode these checks exist to catch, using the smallest
fixture that exhibits it.
"""

import pathlib

import pandas as pd
import pytest

from portugal_refining_resilience.claims import (
    check_bundle_within_window,
    check_claim_matrix,
    check_event_interval,
    check_flagged_cells_have_sensitivity,
    check_prose_numbers,
    check_prose_statistics,
    check_prose_uses_licensed_models,
    check_quantities_are_checkable,
    check_sensitivity_survival,
    check_stated_sample_sizes,
    claim_matrix_rows,
    document_sections,
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
    """A table may carry coefficients from a superseded model run."""
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
    """A stated sample size may belong to a window the model no longer uses."""
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
    """An interval stated in words must match the configured event dates."""
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


def _bundle_dir(tmp_path: pathlib.Path, **files: pd.DataFrame) -> pathlib.Path:
    for name, frame in files.items():
        frame.to_csv(tmp_path / f"{name}.csv", index=False)
    return tmp_path


def test_bundle_within_window_accepts_a_trimmed_bundle(tmp_path: pathlib.Path) -> None:
    inputs = _bundle_dir(
        tmp_path, panel=pd.DataFrame({"year": [1990, 2010, 2024], "value": [1.0, 2.0, 3.0]})
    )

    passed, _ = check_bundle_within_window(inputs, start_year=1990, end_year=2024)

    assert passed is True


def test_bundle_within_window_catches_a_year_the_study_excludes(
    tmp_path: pathlib.Path,
) -> None:
    """Eurostat published 2025 and the comparison was never trimmed.

    A stability claim was then written against a series the paper does not include.
    """
    inputs = _bundle_dir(tmp_path, panel=pd.DataFrame({"year": [2024, 2025], "value": [1.0, 2.0]}))

    passed, detail = check_bundle_within_window(inputs, start_year=1990, end_year=2024)

    assert passed is False
    assert "2025" in detail
    assert "panel.csv" in detail


def test_bundle_within_window_honours_a_declared_exemption(
    tmp_path: pathlib.Path,
) -> None:
    """A source-coverage diagnostic describes the source, not the analysis."""
    inputs = _bundle_dir(
        tmp_path, completeness=pd.DataFrame({"year": [2024, 2026], "months": [12, 5]})
    )

    passed, detail = check_bundle_within_window(
        inputs, start_year=1990, end_year=2024, exempt={"completeness.csv"}
    )

    assert passed is True
    assert "1 declared exemption" in detail


def test_bundle_within_window_ignores_files_with_no_year(
    tmp_path: pathlib.Path,
) -> None:
    inputs = _bundle_dir(
        tmp_path, coefficients=pd.DataFrame({"term": ["const"], "estimate": [0.5]})
    )

    passed, _ = check_bundle_within_window(inputs, start_year=1990, end_year=2024)

    assert passed is True


STATS = r"""
The pair does not reject no-cointegration (Engle--Granger $p=0.088$), and the break is
clear ($F=22.0$, adjusted $p<0.001$).
"""


def _typed_bundle() -> list[pd.DataFrame]:
    """A bundle where 0.088 exists, but not as a p-value."""
    return [
        pd.DataFrame({"cointegration_p_value": [0.0218, 0.000053]}),
        pd.DataFrame({"p_value": [0.005, 0.0001]}),
        pd.DataFrame({"f_statistic": [22.0, 3.1]}),
        pd.DataFrame({"gross_import_dependence": [0.0884, 0.5]}),
    ]


def test_prose_statistics_catches_a_p_value_that_is_only_a_coincidence() -> None:
    """0.088 stopped being the diesel cointegration p-value and nothing noticed.

    ``check_prose_numbers`` accepted it because an import-dependence ratio sits within
    half a printed unit. A p-value has to match something that is a p-value.
    """
    passed, detail = check_prose_statistics(STATS, _typed_bundle())

    assert passed is False
    assert "0.088" in detail


def test_prose_statistics_accepts_a_current_p_value() -> None:
    current = STATS.replace("$p=0.088$", "$p=0.022$")

    passed, _ = check_prose_statistics(current, _typed_bundle())

    assert passed is True


def test_prose_statistics_honours_the_comparison() -> None:
    """``p<0.001`` asserts a bound, so it must not be matched as an equality."""
    passed, _ = check_prose_statistics(
        r"the break is clear ($F=22.0$, adjusted $p<0.001$)", _typed_bundle()
    )

    assert passed is True


def test_prose_statistics_checks_f_against_f_columns() -> None:
    wrong = STATS.replace("$F=22.0$", "$F=99.9$").replace("$p=0.088$", "$p=0.022$")

    passed, detail = check_prose_statistics(wrong, _typed_bundle())

    assert passed is False
    assert "99.9" in detail


def test_claim_matrix_reads_every_table_a_row_cites(
    matrix_sources: dict[str, list[pd.DataFrame]],
) -> None:
    """A row comparing the licensed model with another must be checkable against both."""
    row = MATRIX.replace(
        "Diesel elasticity reaches $1.01$ & Table~\\ref{tab:price}",
        "Diesel elasticity reaches $1.01$, or $1.0072$ in the other & "
        "Tables~\\ref{tab:price}, \\ref{tab:monthly}",
    )

    passed, _ = check_claim_matrix(row, matrix_sources, [])

    assert passed is True


LICENSED = [0.712923, 1.241846, -0.132632, -0.466174]
SUPERSEDED = [0.734831, 1.007214, 0.272383]

FAMILY_TEX = """
\\section{Conclusions}
\\label{sec:conclusions}

On prices, the contemporaneous elasticity of Portuguese to Spanish pre-tax diesel prices
rises from $0.73$ to approximately $1.01$.
"""


def _family(tex: str, allowed: set[str] | None = None) -> tuple[bool, str]:
    return check_prose_uses_licensed_models(
        tex,
        licensed_estimates=LICENSED,
        superseded_estimates=SUPERSEDED,
        may_cite_superseded=allowed or {"sec:shortrun"},
    )


def test_licensed_family_catches_a_conclusion_from_a_superseded_model() -> None:
    """Correcting the model choice changed which numbers the paper may headline.

    Both figures are real estimates from a model that was fitted and persisted. What
    is wrong is that the diagnostics did not select that model, and no reproducibility
    check can see the difference.
    """
    passed, detail = _family(FAMILY_TEX)

    assert passed is False
    assert "sec:conclusions" in detail


def test_licensed_family_accepts_the_licensed_numbers() -> None:
    current = FAMILY_TEX.replace("$0.73$", "$0.713$").replace("$1.01$", "$1.242$")

    passed, _ = _family(current)

    assert passed is True


def test_licensed_family_allows_a_section_whose_subject_is_the_old_model() -> None:
    """Reporting what the discarded specification said is the point in that section."""
    passed, _ = _family(FAMILY_TEX, allowed={"sec:conclusions"})

    assert passed is True


def test_licensed_family_allows_an_attributed_comparison() -> None:
    """Quoting a superseded figure is fine when the prose says where it comes from."""
    attributed = FAMILY_TEX.replace(
        "approximately $1.01$.",
        "approximately $1.242$. Section~\\ref{sec:shortrun} puts it at $1.01$.",
    ).replace("$0.73$", "$0.713$")

    passed, _ = _family(attributed)

    assert passed is True


def test_licensed_family_ignores_a_paragraph_that_is_not_about_prices() -> None:
    """0.800 diesel coverage sits within a printed unit of a 0.7997 elasticity."""
    unrelated = """
\\section{Robustness}
\\label{sec:windows}

Diesel refinery output coverage falls from $1.083$ to $0.735$.
"""

    passed, _ = _family(unrelated)

    assert passed is True


def test_document_sections_labels_by_the_first_section_label() -> None:
    sections = document_sections(FAMILY_TEX)

    assert [label for label, _ in sections] == ["sec:conclusions"]


BARE = r"""
\\section{Diesel}
\\label{sec:diesel}

By 2023 output covers only 66 per cent of demand, against 70 to 96 per cent earlier.
"""


def test_quantity_lint_catches_a_percentage_outside_math_mode() -> None:
    """A bare "66 per cent" against a ratio of 0.678 is invisible to every numeric check.

    They all read math mode, so a percentage written out in words reaches none of them.
    """
    passed, detail = check_quantities_are_checkable(BARE)

    assert passed is False
    assert "66 per cent" in detail


def test_quantity_lint_reads_both_ends_of_a_range() -> None:
    """ "70 to 96 per cent" states two claims and only one sits next to the unit."""
    passed, detail = check_quantities_are_checkable(BARE)

    assert passed is False
    assert "70" in detail or "96" in detail


def test_quantity_lint_accepts_math_mode() -> None:
    fixed = BARE.replace("66 per cent", "$0.678$").replace("70 to 96 per cent", "$0.70$ to $0.96$")

    passed, _ = check_quantities_are_checkable(fixed)

    assert passed is True


def test_quantity_lint_exempts_tables_and_the_matrix() -> None:
    """Table values have a stricter check of their own against a declared source."""
    table = r"""
\\section{X}
\\begin{table}
\\begin{tabular}{lr}
2023 & 68 per cent \\\\
\\end{tabular}
\\end{table}
"""

    passed, _ = check_quantities_are_checkable(table)

    assert passed is True


def test_quantity_lint_honours_the_allow_list() -> None:
    """A stated tolerance is not a measurement and has nothing to reproduce from."""
    threshold = "\\section{X}\n\nApplying a 25 kt floor to the comparison.\n"

    assert check_quantities_are_checkable(threshold)[0] is False
    assert check_quantities_are_checkable(threshold, allow={25.0})[0] is True
