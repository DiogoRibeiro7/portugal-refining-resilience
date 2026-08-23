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


def test_archive_dois_agree_between_citation_and_readme() -> None:
    """The version DOI has to be changed by hand at each release, in two files.

    The concept DOI never changes; the version DOI does, and a stale one silently cites the
    wrong archive. That is the same failure this module already guards for version strings.
    """
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    version_doi = citation["doi"]
    concept = [entry for entry in citation["identifiers"] if entry["type"] == "doi"]
    assert len(concept) == 1, "expected exactly one concept DOI identifier"
    concept_doi = concept[0]["value"]

    assert version_doi != concept_doi, "the version DOI must not be the concept DOI"
    for doi in (version_doi, concept_doi):
        assert doi.startswith("10.5281/zenodo."), doi
        assert doi in readme, f"{doi} is in CITATION.cff but not the README"
