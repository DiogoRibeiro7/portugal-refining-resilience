"""Argument handling for the pipeline runner.

The earlier version tested for one flag by membership in ``sys.argv`` and ignored everything
else, so an unrecognised argument silently meant "run every notebook against the live sources".
That is how ``--help`` came to trigger a full ten-minute run.

Nothing here executes a notebook. These call ``build_parser`` rather than ``main`` on purpose:
an earlier draft of this file called ``main`` with a mistyped flag, argparse resolved the typo
to ``--save-outputs`` by prefix matching, and the test started the whole pipeline with
output-saving on. A test for argument handling should not be able to reach the work.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_notebooks  # noqa: E402


def parse(argv: list[str]) -> object:
    return run_notebooks.build_parser().parse_args(argv)


def test_no_selection_runs_the_whole_pipeline() -> None:
    paths = run_notebooks.select()
    assert paths == sorted(paths)
    assert len(paths) > 1


def test_selection_keeps_filename_order_not_argument_order() -> None:
    assert [path.name[:2] for path in run_notebooks.select("20,19")] == ["19", "20"]


def test_single_digit_numbers_are_padded() -> None:
    assert run_notebooks.select("4") == run_notebooks.select("04")


def test_a_shared_number_selects_every_notebook_carrying_it() -> None:
    """Two notebooks are numbered 14, and asking for 14 must not quietly run only one."""
    chosen = [path.name for path in run_notebooks.select("14")]
    assert chosen == ["14_2022_stress_test.ipynb", "14_monthly_event_analysis.ipynb"]


def test_unknown_notebook_number_is_refused() -> None:
    with pytest.raises(ValueError, match="99"):
        run_notebooks.select("19,99")


def test_empty_selection_is_refused() -> None:
    with pytest.raises(ValueError):
        run_notebooks.select(" , ")


def test_outputs_are_discarded_unless_asked_for() -> None:
    assert parse([]).save_outputs is False
    assert parse(["--save-outputs"]).save_outputs is True


@pytest.mark.parametrize("argv", [["--nonsense"], ["19"], ["--only"], ["--save-outputs=yes"]])
def test_unrecognised_arguments_are_refused(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        parse(argv)
    assert exit_info.value.code != 0


@pytest.mark.parametrize("typo", ["--save-output", "--save", "--sa"])
def test_abbreviations_do_not_reach_the_destructive_flag(typo: str) -> None:
    """A prefix of ``--save-outputs`` must not be accepted as ``--save-outputs``.

    Argparse allows abbreviated long options unless told otherwise, so without
    ``allow_abbrev=False`` a typo rewrites every notebook with execution state.
    """
    with pytest.raises(SystemExit) as exit_info:
        parse([typo])
    assert exit_info.value.code != 0
