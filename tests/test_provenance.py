"""Keep `reports/data_provenance.md` in step with the report it maps.

The document is the only route from a printed number back to the file it came from, since
the paper does not name internal files. Its table numbering had drifted six rows, so a reader
checking Table 12 was sent to the file behind Table 9, and half the evidence bundle was
undocumented. Neither failure is visible by reading the document on its own.

`scripts/refresh_provenance.py` regenerates the two mapping sections; these tests fail when
someone edits the report without rerunning it.
"""

import re
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DOC = (ROOT / "reports" / "data_provenance.md").read_text(encoding="utf-8")
TEX = (ROOT / "reports" / "report_final.tex").read_text(encoding="utf-8")
MAPPING = yaml.safe_load((ROOT / "config" / "report_tables.yml").read_text(encoding="utf-8"))

NARRATIVE = "narrative; see below"


def _labels(kind: str) -> list[str]:
    """Labels in source order, which is the order LaTeX numbers them."""
    return re.findall("label[{](" + kind + ":[^}]+)[}]", TEX)


def _section(heading: str) -> str:
    body = DOC.split("## " + heading + "\n", 1)[1]
    return body.split("\n## ", 1)[0]


def _rows(heading: str) -> list[tuple[int, str]]:
    """(number, third column) for each row of a mapping table."""
    found = re.findall(r"^\| (\d+) \| [^|]+ \| ([^|]+) \|", _section(heading), re.MULTILINE)
    return [(int(number), cell.strip()) for number, cell in found]


def test_table_numbering_matches_the_report() -> None:
    labels = _labels("tab")
    rows = _rows("Tables")
    assert [number for number, _ in rows] == list(range(1, len(labels) + 1))

    sources = MAPPING["tables"]
    for (number, cell), label in zip(rows, labels, strict=True):
        declared = sources.get(label)
        expected = ", ".join(f"`{name}`" for name in declared) if declared else NARRATIVE
        assert cell == expected, f"table {number} ({label}) documented as {cell}"


def test_figure_numbering_matches_the_report() -> None:
    numbers = [number for number, _ in _rows("Figures")]
    assert numbers == list(range(1, len(_labels("fig")) + 1))


@pytest.mark.parametrize("suffix", ["*.csv", "*.png"])
def test_every_bundle_artifact_is_documented(suffix: str) -> None:
    bundle = sorted(path.name for path in (ROOT / "artifacts" / "report_inputs").glob(suffix))
    assert bundle, f"no {suffix} in the evidence bundle"
    undocumented = [name for name in bundle if name not in DOC]
    assert not undocumented, f"not named in the provenance document: {undocumented}"


def test_documented_files_exist_in_the_bundle() -> None:
    """The reverse direction: a row pointing at a file that was renamed away."""
    named = set(re.findall(r"`([a-z0-9_]+\.csv)`", DOC))
    external = {path.name for path in (ROOT / "data" / "reference").glob("*.csv")}
    external |= {path.name for path in (ROOT / "data" / "metrics").glob("*.csv")}
    bundle = {path.name for path in (ROOT / "artifacts" / "report_inputs").glob("*.csv")}
    missing = sorted(named - bundle - external)
    assert not missing, f"documented but not present: {missing}"


WORDS = {8: "eight", 12: "twelve"}


def test_stated_check_counts_match_the_gate() -> None:
    """The counts are spelled out in prose in two files and nothing recomputes them.

    Both were written when the gate had five claim checks, and both were wrong by the time it
    had eleven.
    """
    metrics = ROOT / "data" / "metrics"
    readiness = len(pd.read_csv(metrics / "report_readiness.csv"))
    claims = len(pd.read_csv(metrics / "report_claim_checks.csv"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert f"{WORDS[readiness]} readiness checks" in readme, f"README miscounts {readiness}"
    assert f"{WORDS[claims]} claim" in readme, f"README miscounts {claims}"
    assert f"{WORDS[claims].capitalize()} checks run in total" in DOC
    assert f"all {WORDS[readiness]} checks pass" in DOC


def _report_numbers() -> str:
    """The report's text with LaTeX thousand separators flattened, plus a comma-free copy."""
    flat = TEX.replace("{,}", ",")
    return flat + "\n" + flat.replace(",", "")


def test_summary_quotes_no_figure_the_report_lacks() -> None:
    """`report_final.md` restates the report, so its figures must be findable there.

    The gate checks `report_final.tex` and `article.tex`; nothing checked the summary, and it
    drifted a whole release behind while stating that its figures were gate-verified. It quoted
    a superseded weekly sample size, adjustment speeds, half-lives and elasticities.

    This is containment, not verification: a number could still be quoted out of the wrong
    column of the right report. It catches drift between the two documents, which is what
    actually happened.
    """
    summary = (ROOT / "reports" / "report_final.md").read_text(encoding="utf-8")
    haystack = _report_numbers()

    missing: dict[str, str] = {}
    for line in summary.splitlines():
        for match in re.finditer(r"\d[\d,]*\.?\d*", line):
            token = match.group(0).rstrip(".")
            if token not in haystack and token.replace(",", "") not in haystack:
                missing.setdefault(token, line.strip())

    assert not missing, "quoted in the summary but not in the report: " + ", ".join(
        f"{token} ({line[:60]})" for token, line in missing.items()
    )


def test_superseded_documents_say_so_in_themselves() -> None:
    """A warning that lives only in a sibling README is not reached by a direct link.

    `report_final.md` was trusted because a sentence in it claimed the gate covered it. The
    archive has the mirror-image problem: `archive/README.md` explains that those documents are
    superseded, and someone opening `report_v1.md` from a file listing or the Zenodo archive
    never sees it.
    """
    archived = sorted(
        path for path in (ROOT / "reports" / "archive").glob("*.md") if path.name != "README.md"
    )
    assert archived, "no archived documents found"

    unmarked = [
        path.name for path in archived if "Superseded" not in path.read_text(encoding="utf-8")[:600]
    ]
    assert not unmarked, f"archived without a notice in the file itself: {unmarked}"
