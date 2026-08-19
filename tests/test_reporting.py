"""Tests for the report bundle.

The bundle is what report-writing prompts are allowed to treat as evidence, so the
manifest has to account for every file in the directory and refuse to claim
completeness when something is absent.
"""

import json
from pathlib import Path

import pytest

from portugal_refining_resilience.io import sha256_file
from portugal_refining_resilience.reporting import build_report_bundle


def _source(tmp_path: Path, name: str, content: str = "year,value\n2021,1\n") -> Path:
    path = tmp_path / "source" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_build_report_bundle_copies_and_checksums(tmp_path: Path) -> None:
    destination = tmp_path / "bundle"
    panel = _source(tmp_path, "panel.csv")

    manifest = build_report_bundle(destination=destination, files=[panel])

    assert manifest["complete"] is True
    entry = manifest["files"][0]  # type: ignore[index]
    assert entry["file"] == "panel.csv"
    assert entry["kind"] == "data"
    assert entry["sha256"] == sha256_file(destination / "panel.csv")
    assert (destination / "panel.csv").read_text(encoding="utf-8") == panel.read_text(
        encoding="utf-8"
    )


def test_build_report_bundle_records_figures_separately(tmp_path: Path) -> None:
    destination = tmp_path / "bundle"
    panel = _source(tmp_path, "panel.csv")
    figure = _source(tmp_path, "chart.png", "not-really-a-png")

    manifest = build_report_bundle(destination=destination, files=[panel], figures=[figure])

    kinds = {entry["file"]: entry["kind"] for entry in manifest["files"]}  # type: ignore[union-attr]
    assert kinds == {"panel.csv": "data", "chart.png": "figure"}
    assert (destination / "chart.png").exists()


def test_build_report_bundle_removes_unmanifested_files(tmp_path: Path) -> None:
    """A stale file in a checksum-protected directory is evidence nobody vouched for."""
    destination = tmp_path / "bundle"
    destination.mkdir()
    (destination / "leftover.csv").write_text("stale\n", encoding="utf-8")
    panel = _source(tmp_path, "panel.csv")

    manifest = build_report_bundle(destination=destination, files=[panel])

    assert manifest["removed_unmanifested"] == ["leftover.csv"]
    assert not (destination / "leftover.csv").exists()
    names = {path.name for path in destination.iterdir()}
    assert names == {"panel.csv", "report_manifest.json"}


def test_build_report_bundle_manifest_accounts_for_every_file(tmp_path: Path) -> None:
    destination = tmp_path / "bundle"
    files = [_source(tmp_path, f"table_{index}.csv") for index in range(3)]
    figures = [_source(tmp_path, "chart.png", "png")]

    manifest = build_report_bundle(destination=destination, files=files, figures=figures)

    manifested = {entry["file"] for entry in manifest["files"]}  # type: ignore[union-attr]
    on_disk = {path.name for path in destination.iterdir()} - {"report_manifest.json"}
    assert manifested == on_disk


def test_build_report_bundle_raises_when_required_input_is_missing(tmp_path: Path) -> None:
    destination = tmp_path / "bundle"
    panel = _source(tmp_path, "panel.csv")
    absent = tmp_path / "source" / "never_generated.csv"

    with pytest.raises(FileNotFoundError, match="Report bundle incomplete"):
        build_report_bundle(destination=destination, files=[panel, absent], required=True)

    # The manifest is still written so the failure is auditable.
    manifest = json.loads((destination / "report_manifest.json").read_text(encoding="utf-8"))
    assert manifest["complete"] is False
    assert manifest["missing"] == [str(absent)]


def test_build_report_bundle_can_report_incompleteness_without_raising(tmp_path: Path) -> None:
    destination = tmp_path / "bundle"
    absent = tmp_path / "source" / "never_generated.csv"

    manifest = build_report_bundle(destination=destination, files=[absent], required=False)

    assert manifest["complete"] is False
    assert manifest["files"] == []
