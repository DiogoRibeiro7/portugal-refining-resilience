"""Rebuild the table and figure mappings in `reports/data_provenance.md`.

The numbering is read from `reports/report_final.aux` and the file behind each table from
`config/report_tables.yml`, so the document cannot claim a number the build does not assign.
It had drifted six rows out of step before this existed, which sent a reader checking one
table to the file behind another.

Adding a table or figure to the report makes this script fail until the description below is
filled in, which is the point: a silent fallback would reintroduce the drift in a quieter form.

Run after `make report-pdf`, since it reads the `.aux` that build writes.
"""

from __future__ import annotations

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
AUX_PATH = ROOT / "reports" / "report_final.aux"
DOC_PATH = ROOT / "reports" / "data_provenance.md"
MAPPING_PATH = ROOT / "config" / "report_tables.yml"

# Short caption and producing notebook for each label, in the report's own words.
TABLES: dict[str, tuple[str, str]] = {
    "tab:coverage": ("Source coverage", "`07`-`09`, `04`"),
    "tab:diesel": ("Diesel annual balance", "`10_build_analytical_panel.ipynb`"),
    "tab:gasoline": ("Gasoline annual balance", "`10_build_analytical_panel.ipynb`"),
    "tab:headline": ("Balance at the event years", "`18`, `06`"),
    "tab:breaks": ("Chow tests at candidate break years", "`13_structural_breaks.ipynb`"),
    "tab:its": (
        "Interrupted-trend models, both 2022 specifications",
        "`13_structural_breaks.ipynb`",
    ),
    "tab:phases": ("Diesel monthly phase means", "`14_monthly_event_analysis.ipynb`"),
    "tab:monthly": (
        "Segmented monthly event model, both specifications",
        "`14_monthly_event_analysis.ipynb`",
    ),
    "tab:stresssens": ("2022 diesel exports by trade source", "`14_2022_stress_test.ipynb`"),
    "tab:price": (
        "Contemporaneous elasticity, difference-only model",
        "`15_price_comovement.ipynb`",
    ),
    "tab:ecm": ("Error-correction models", "`15_price_comovement.ipynb`"),
    "tab:ecmbreak": (
        "Adjustment speed with the long-run relation fixed and shifted",
        "`15_price_comovement.ipynb`",
    ),
    "tab:spain": ("Diesel balance ratios, Portugal against Spain", "`16_spain_comparison.ipynb`"),
    "tab:windows": ("Pre/post difference by window", "`17_robustness_and_sensitivity.ipynb`"),
    "tab:claims": (
        "Claim-evidence matrix",
        "written prose; every row checked against the table it cites",
    ),
    "tab:armrecon": (
        "Monthly arm against annual arm, four balance terms",
        "`17_robustness_and_sensitivity.ipynb`",
    ),
    "tab:sourcesens": (
        "2022 interrupted-trend level changes by source",
        "`17_robustness_and_sensitivity.ipynb`",
    ),
}

FIGURES: dict[str, tuple[str, str, str]] = {
    "fig:dieselbalance": ("Diesel physical balance", "`diesel_physical_balance.png`", "`11`"),
    "fig:gasbalance": ("Gasoline physical balance", "`gasoline_physical_balance.png`", "`11`"),
    "fig:dieselratios": ("Diesel dependence ratios", "`diesel_dependence_ratios.png`", "`12`"),
    "fig:gasratios": ("Gasoline dependence ratios", "`gasoline_dependence_ratios.png`", "`12`"),
    "fig:monthlydieselratio": (
        "Monthly diesel net imports to demand",
        "`monthly_event_diesel_net_import_to_demand_ratio.png`",
        "`14`",
    ),
    "fig:monthlydiesel": (
        "Monthly diesel imports and exports",
        "`monthly_event_diesel_imports_kt.png`, `monthly_event_diesel_exports_kt.png`",
        "`14`",
    ),
    "fig:monthlygas": (
        "Monthly gasoline imports and exports",
        "`monthly_event_gasoline_imports_kt.png`, `monthly_event_gasoline_exports_kt.png`",
        "`14`",
    ),
    "fig:monthlygasratio": (
        "Monthly gasoline net imports to demand",
        "`monthly_event_gasoline_net_import_to_demand_ratio.png`",
        "`14`",
    ),
    "fig:spreads": (
        "PT-ES pre-tax price spreads",
        "`pt_es_diesel_pretax_price_spread.png`, `pt_es_gasoline_pretax_price_spread.png`",
        "`16`",
    ),
    "fig:spainfull": (
        "PT and ES diesel coverage, full window",
        "`pt_es_diesel_output_ratio_full_window.png`",
        "`16`",
    ),
}

HEADER = (
    "Generated from `reports/report_final.aux` and `config/report_tables.yml` by\n"
    "`scripts/refresh_provenance.py`, so the numbering cannot drift from the built document.\n"
)


def numbered(aux: str, prefix: str) -> list[tuple[str, str]]:
    """Labels of the given kind, in the order the build numbered them."""
    found = re.findall(r"newlabel\{(" + prefix + r":[^}]+)\}\{\{([^}]+)\}", aux)
    return sorted(dict(found).items(), key=lambda item: int(item[1]))


def main() -> int:
    """Rewrite the two mapping sections in place."""
    if not AUX_PATH.exists():
        print(f"{AUX_PATH} not found; run `make report-pdf` first", file=sys.stderr)
        return 1

    aux = AUX_PATH.read_text(encoding="utf-8", errors="replace")
    sources = yaml.safe_load(MAPPING_PATH.read_text(encoding="utf-8")).get("tables", {})

    tables = numbered(aux, "tab")
    figures = numbered(aux, "fig")

    undescribed = [label for label, _ in tables if label not in TABLES]
    undescribed += [label for label, _ in figures if label not in FIGURES]
    if undescribed:
        print(
            "no description for " + ", ".join(undescribed) + "; add it to this script",
            file=sys.stderr,
        )
        return 1

    rows = []
    for label, number in tables:
        caption, notebook = TABLES[label]
        files = sources.get(label)
        cell = ", ".join(f"`{name}`" for name in files) if files else "narrative; see below"
        rows.append(f"| {number} | {caption} | {cell} | {notebook} |")

    tables_block = (
        "## Tables\n\n"
        + HEADER
        + "\n| Table | Caption | Derived file | Produced by |\n|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n"
    )

    figure_rows = []
    for label, number in figures:
        caption, image, notebook = FIGURES[label]
        figure_rows.append(f"| {number} | {caption} | {image} | {notebook} |")

    figures_block = (
        "## Figures\n\n| Figure | Caption | Image | Produced by |\n|---|---|---|---|\n"
        + "\n".join(figure_rows)
        + "\n"
    )

    text = DOC_PATH.read_text(encoding="utf-8")
    text = re.sub(r"## Tables\n.*?(?=## Figures)", tables_block + "\n", text, flags=re.S)
    text = re.sub(r"## Figures\n.*?(?=## Numbers quoted)", figures_block + "\n", text, flags=re.S)
    DOC_PATH.write_text(text, encoding="utf-8")

    print(f"{len(rows)} tables, {len(figure_rows)} figures written to {DOC_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
