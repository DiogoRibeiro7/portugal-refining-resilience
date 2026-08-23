"""Run the gate, rather than trusting the results it left behind.

CI runs pytest, ruff and mypy. It never ran the readiness or claim checks, so the machinery that
ties every number in the report to the file behind it only ever executed on the machine of
whoever last ran notebook 20, and CI read the committed results CSV as though it were evidence.
A CSV saying the checks passed is a record that they once passed, not that they pass now.

Nothing here needs the network or a notebook run: the evidence bundle, both documents and the
configuration are all committed, and the whole gate takes a few seconds against them.

The article is deliberately not blocking. Notebook 20 reports its failures rather than raising,
on the grounds that a second document should not be able to break the pipeline that produces the
report, and that decision is left alone here.
"""

from pathlib import Path

import pandas as pd

from portugal_refining_resilience.config import get_paths
from portugal_refining_resilience.readiness import (
    build_readiness_checks,
    build_report_claim_checks,
)

ROOT = Path(__file__).resolve().parents[1]
PATHS = get_paths(ROOT)

# The checks notebook 20 refuses to publish without.
PUBLICATION_BLOCKERS = [
    "core_report_bundle_complete",
    "trade_not_seed_only",
    "jodi_annual_completeness_valid",
    "monthly_event_panel_valid",
    "monthly_event_outputs_valid",
    "eurostat_balance_available",
    "dgeg_trade_reconciliation_valid",
]


def _readiness() -> pd.DataFrame:
    manifest = PATHS.report_inputs / "report_manifest.json"
    return pd.DataFrame(build_readiness_checks(PATHS, manifest_path=manifest))


def test_publication_blocking_readiness_checks_pass() -> None:
    checks = _readiness()
    blocking = checks[checks["check"].isin(PUBLICATION_BLOCKERS)]
    assert len(blocking) == len(PUBLICATION_BLOCKERS), "a blocking check disappeared"
    failed = blocking.loc[~blocking["passed"], "check"].tolist()
    assert not failed, f"readiness checks failed: {failed}"


def test_the_report_still_agrees_with_the_evidence_bundle() -> None:
    """Every number the report prints must still be reproducible from its declared source."""
    checks = build_report_claim_checks(PATHS)
    failed = checks.loc[~checks["passed"], "check"].tolist()
    assert not failed, f"the report disagrees with the evidence bundle: {failed}"


def test_committed_gate_results_are_not_stale() -> None:
    """The committed CSVs must describe the gate as it is now.

    Other tests read these files to check that prose states the right number of checks. That is
    only meaningful if the files themselves are current.
    """
    for name, live in (
        ("report_readiness.csv", _readiness()),
        ("report_claim_checks.csv", build_report_claim_checks(PATHS)),
    ):
        committed = pd.read_csv(PATHS.metrics / name)
        assert sorted(committed["check"]) == sorted(live["check"]), (
            f"{name} lists different checks than the gate runs; rerun notebook 20"
        )
