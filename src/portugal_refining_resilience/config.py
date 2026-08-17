from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """Canonical project directories."""

    root: Path
    data: Path
    raw: Path
    interim: Path
    processed: Path
    metrics: Path
    provenance: Path
    reference: Path
    figures: Path
    tables: Path
    report_inputs: Path


def find_project_root(start: Path | None = None) -> Path:
    """Find the repository root by locating ``pyproject.toml``."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists():
            return candidate
    raise FileNotFoundError("Could not locate project root containing pyproject.toml")


def get_paths(start: Path | None = None) -> ProjectPaths:
    """Return all project paths and create writable output directories."""
    root = find_project_root(start)
    paths = ProjectPaths(
        root=root,
        data=root / "data",
        raw=root / "data" / "raw",
        interim=root / "data" / "interim",
        processed=root / "data" / "processed",
        metrics=root / "data" / "metrics",
        provenance=root / "data" / "provenance",
        reference=root / "data" / "reference",
        figures=root / "figures",
        tables=root / "tables",
        report_inputs=root / "artifacts" / "report_inputs",
    )
    for directory in (
        paths.raw,
        paths.interim,
        paths.processed,
        paths.metrics,
        paths.provenance,
        paths.reference,
        paths.figures,
        paths.tables,
        paths.report_inputs,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return paths
