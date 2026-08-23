"""The figures the report embeds must be the figures the bundle vouches for.

`report_final.tex` sets `\\graphicspath{{../figures/}{../artifacts/report_inputs/}}`, so a
figure is taken from `figures/` when one exists there and from the evidence bundle otherwise.
`figures/` is not covered by `report_manifest.json`. The manifest therefore records a checksum
for a copy the document does not use, and if the two ever diverge the report would show one
image while the protected evidence held another, with nothing to say so.

They are identical today. This keeps them that way.
"""

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"
BUNDLE = ROOT / "artifacts" / "report_inputs"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rendered() -> list[Path]:
    return sorted(FIGURES.glob("*.png"))


def test_there_are_figures_to_compare() -> None:
    assert _rendered(), "no figures found; the comparison below would pass vacuously"


@pytest.mark.parametrize("figure", _rendered(), ids=lambda path: path.name)
def test_rendered_figure_matches_the_bundled_copy(figure: Path) -> None:
    bundled = BUNDLE / figure.name
    assert bundled.exists(), f"{figure.name} is embedded by the report but not in the bundle"
    assert _digest(figure) == _digest(bundled), (
        f"{figure.name} differs between figures/ and the evidence bundle; "
        "the report embeds the figures/ copy, which the manifest does not cover"
    )
