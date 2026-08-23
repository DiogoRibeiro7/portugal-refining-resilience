"""Keep every version-bearing file in step.

v0.1.1 was tagged and released while ``pyproject.toml``, ``__init__.py`` and
``.zenodo.json`` all still declared 0.1.0, so the drift is not hypothetical.
"""

import json
import re
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


def test_citation_carries_the_concept_doi() -> None:
    """``doi`` must be the concept DOI, not a version DOI.

    Zenodo mints a version DOI at deposit, which is after the release is tagged, so a version
    DOI written here is wrong from the moment it is written: 0.5.1 would have shipped carrying
    the DOI of 0.5.0. The concept DOI resolves to whichever version is latest and never goes
    stale. Version DOIs are listed in the README, where each is labelled by version.
    """
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    concept_row = re.search(
        r"\[(10\.5281/zenodo\.\d+)\]\([^)]*\)\s*\|\s*whichever version is latest", readme
    )
    assert concept_row, "the README table has no row for the concept DOI"
    assert citation["doi"] == concept_row.group(1), (
        "CITATION.cff doi is not the concept DOI the README designates"
    )

    for entry in citation.get("identifiers", []):
        if entry["type"] != "doi":
            continue
        assert entry["value"].startswith("10.5281/zenodo."), entry
        assert entry["value"] in readme, f"{entry['value']} is in CITATION.cff but not the README"
