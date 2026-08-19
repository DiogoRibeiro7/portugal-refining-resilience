from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml


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


def load_analysis_config(root: Path | None = None) -> dict[str, Any]:
    """Load ``config/analysis.yml``.

    Analytical windows, event dates and source-reconciliation tolerances live in
    configuration rather than in code so that changing them is a reviewable decision.
    """
    base = root or find_project_root()
    payload: Any = yaml.safe_load((base / "config" / "analysis.yml").read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("analysis"), dict):
        raise ValueError("analysis.yml must contain a top-level 'analysis' mapping")
    return cast("dict[str, Any]", payload["analysis"])
