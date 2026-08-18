"""Keep every version-bearing file in step.

v0.1.1 was tagged and released while ``pyproject.toml``, ``__init__.py`` and
``.zenodo.json`` all still declared 0.1.0, so the drift is not hypothetical.
"""

import json
import tomllib
from pathlib import Path

import yaml

import portugal_refining_resilience

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version: str = payload["project"]["version"]
    return version


def test_package_version_matches_pyproject() -> None:
    assert portugal_refining_resilience.__version__ == _pyproject_version()


def test_zenodo_metadata_matches_pyproject() -> None:
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    version = _pyproject_version()

    assert zenodo["version"] == version
    identifiers = [entry["identifier"] for entry in zenodo["related_identifiers"]]
    assert any(identifier.endswith(f"/releases/tag/v{version}") for identifier in identifiers), (
        f"No release identifier points at v{version}: {identifiers}"
    )


def test_citation_version_matches_pyproject() -> None:
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert citation["version"] == _pyproject_version()


def test_release_dates_agree() -> None:
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert str(citation["date-released"]) == zenodo["publication_date"]
