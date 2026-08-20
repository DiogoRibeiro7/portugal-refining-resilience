"""Verify that the written report agrees with the evidence bundle.

The readiness gate establishes that evidence exists, is complete and reconciles. It
cannot establish that the prose uses it correctly, and three separate defects reached a
finished draft through that gap: a table quoting a coefficient the pipeline no longer
produced, a stated sample size belonging to an earlier window, and a headline statistic
computed from the one trade cell the reconciliation had flagged as an outlier.

The checks here close that gap by reading the report and comparing it against the
bundle it claims to be based on. They are deliberately mechanical: every number in a
labelled table must be reproducible from the file that table is declared to come from,
the sample sizes quoted in the prose must match the fitted models, an interval stated
in words must match the configured event dates, and any cell the reconciliation flags
must have a sensitivity computed for it.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

#: Numbers appear as ``1{,}597``, ``$-$0.24``, ``$-105.21$`` or ``0.66``.
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")

_MONTH_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def _strip_latex(cell: str) -> str:
    """Reduce a table cell to the text a reader sees.

    Commands that take arguments are removed with their arguments. ``\\multicolumn``
    matters most: leaving its column count behind would make a spanning header assert
    that the number 3 appears in the data.
    """
    cell = re.sub(r"\\rlap\{[^{}]*\}", "", cell)
    cell = re.sub(r"\\multicolumn\{[^{}]*\}\{[^{}]*\}\{([^{}]*)\}", r"\1", cell)
    cell = re.sub(r"\\cmidrule(?:\([^)]*\))?\{[^{}]*\}", " ", cell)
    cell = re.sub(r"\\(?:texttt|textbf|emph|quad)\s*", " ", cell)
    cell = cell.replace("{,}", "").replace("$", "").replace("\\", " ")
    return cell.strip()


def parse_latex_tables(tex: str) -> dict[str, list[str]]:
    """Return the body rows of every labelled table, keyed by its label.

    Floats are matched as whole environments so that a table's rows are attributed to
    the label declared inside it, rather than to whatever label happened to appear
    earlier in the document.
    """
    tables: dict[str, list[str]] = {}
    float_pattern = re.compile(
        r"\\begin\{(table|longtable)\}(?:\[[^\]]*\])?(.*?)\\end\{\1\}", re.DOTALL
    )
    for block in float_pattern.finditer(tex):
        body = block.group(2)
        label = re.search(r"\\label\{([^{}]+)\}", body)
        if label is None:
            continue
        inner = body
        tabular = re.search(r"\\begin\{tabular\}.*?\\end\{tabular\}", body, re.DOTALL)
        if tabular is not None:
            inner = tabular.group(0)
        # Rules are stripped from each segment rather than used to discard it: a rule
        # and the row after it share a segment, so discarding would silently drop the
        # first body row of every table.
        rows = []
        for segment in inner.split("\\\\"):
            cleaned = re.sub(
                r"\\(?:top|mid|bottom)rule|\\cmidrule(?:\([^)]*\))?\{[^{}]*\}|\\endhead",
                " ",
                segment,
            )
            if "&" in cleaned and "caption" not in cleaned:
                rows.append(cleaned)
        tables[label.group(1)] = rows
    return tables


def printed_numbers(rows: list[str]) -> list[tuple[float, int]]:
    """Extract each number with the number of decimals it was printed to.

    The printed precision has to come from the text, not from the parsed float: a
    table showing ``622`` is asserting agreement to the nearest unit, whereas Python
    renders that same value as ``622.0`` and would imply a claim ten times tighter.
    """
    found: list[tuple[float, int]] = []
    for row in rows:
        for cell in _strip_latex(row).split("&"):
            for token in _NUMBER.findall(cell.replace(",", "")):
                try:
                    value = float(token)
                except ValueError:  # pragma: no cover - regex guarantees a number
                    continue
                decimals = len(token.split(".")[1]) if "." in token else 0
                found.append((value, decimals))
    return found


def table_numbers(rows: list[str]) -> list[float]:
    """Extract every number a reader would see in the given table rows."""
    return [value for value, _ in printed_numbers(rows)]


def _reproducible(value: float, decimals: int, frames: list[pd.DataFrame]) -> bool:
    """Is ``value`` a rounded form of something in one of the source frames?

    ``decimals`` is the precision the report printed, which sets how close a source
    value has to be. A table showing 622 asserts agreement to the nearest unit.
    """
    # A printed number matches when some source value lies within half a unit of the
    # last printed digit. Comparing re-rounded values instead would make matching
    # depend on tie-breaking, so 122.75 printed as 122.8 would fail.
    tolerance = 0.5 * (10.0**-decimals) + 1e-9
    for frame in frames:
        numeric = frame.select_dtypes("number")
        for column in numeric.columns:
            series = numeric[column].dropna()
            if series.empty:
                continue
            if ((series - value).abs() <= tolerance).any():
                return True
            # ratios are sometimes printed as percentage points
            if ((series - value / 100.0).abs() <= tolerance / 100.0).any():
                return True
    return False


def verify_table_values(
    label: str,
    rows: list[str],
    frames: list[pd.DataFrame],
    *,
    ignore_below: float = 1900.0,
    ignore_above: float | None = None,
) -> list[float]:
    """Return the numbers in a table that no source frame reproduces.

    Values that look like years are skipped: they index the data rather than assert
    anything about it.
    """
    unmatched: list[float] = []
    for value, decimals in printed_numbers(rows):
        if 1900.0 <= value <= 2100.0 and float(value).is_integer():
            continue
        if abs(value) < 1e-9:
            continue
        if ignore_above is not None and abs(value) > ignore_above:
            continue
        if not _reproducible(value, decimals, frames):
            unmatched.append(value)
    _ = (label, ignore_below)
    return unmatched


def check_stated_sample_sizes(
    tex: str, models: pd.DataFrame | list[pd.DataFrame]
) -> tuple[bool, str]:
    """Every ``$n=...$`` in the report must match some fitted model's observation count.

    The report quotes several: the monthly event models, the annual interrupted trends
    and the weekly price models each have their own. A stated size that matches none of
    them is either stale or invented.
    """
    frames = models if isinstance(models, list) else [models]
    actual: set[int] = set()
    for frame in frames:
        if frame.empty:
            continue
        for column in ("n_obs", "nobs"):
            if column in frame.columns:
                actual |= {int(value) for value in frame[column].dropna().unique()}
    if not actual:
        return False, "no model table carries n_obs or nobs"

    stated = {
        int(match.replace(",", "").replace("{", "").replace("}", ""))
        for match in re.findall(r"\$n=([\d{},]+)\$", tex)
    }
    if not stated:
        return True, "no sample size stated in the report"
    wrong = sorted(stated - actual)
    if wrong:
        return False, f"report states n={wrong} but the fitted models report {sorted(actual)}"
    return True, f"stated sample sizes {sorted(stated)} match the fitted models"


def check_event_interval(tex: str, event_dates: dict[str, Any]) -> tuple[bool, str]:
    """An interval written in words must match the configured event dates."""
    start = event_dates.get("matosinhos_closure_start")
    end = event_dates.get("energy_stress_start")
    if not start or not end:
        return True, "event dates not configured; interval not checked"
    first, second = pd.Timestamp(str(start)), pd.Timestamp(str(end))
    months = (second.year - first.year) * 12 + (second.month - first.month)

    written = re.findall(r"fall\s+(?:within\s+)?([a-z]+)\s+months", tex.lower())
    if not written:
        return True, f"no interval stated; configured gap is {months} months"
    wrong = sorted({w for w in written if _MONTH_WORDS.get(w) != months})
    if wrong:
        return (
            False,
            f"report says {wrong} months between the closure and the stress start; "
            f"the configured dates are {months} months apart",
        )
    return True, f"stated interval matches the configured {months}-month gap"


def check_flagged_cells_have_sensitivity(
    reconciliation: pd.DataFrame, sensitivities: list[pd.DataFrame]
) -> tuple[bool, str]:
    """Every disputed trade cell must have had a sensitivity computed.

    A cell the reconciliation flags cannot be quoted as though the sources agreed. This
    does not check the prose; it checks that the alternative was calculated at all, so
    the writer has something to quote.
    """
    if "reconciliation_status" not in reconciliation.columns:
        return False, "reconciliation table missing reconciliation_status"
    flagged = reconciliation.loc[reconciliation["reconciliation_status"].ne("within_tolerance")]
    if flagged.empty:
        return True, "no disputed trade cells"

    covered: set[tuple[int, str]] = set()
    for frame in sensitivities:
        if frame.empty or "product" not in frame.columns:
            continue
        years = frame["year"] if "year" in frame.columns else frame.get("event_year")
        if years is None:
            continue
        covered |= {
            (int(year), str(product)) for year, product in zip(years, frame["product"], strict=True)
        }

    flagged_keys = set(
        zip(
            flagged["year"].astype(int),
            flagged["product"].astype(str),
            strict=True,
        )
    )
    missing = sorted(flagged_keys - covered)
    if missing:
        return False, f"disputed cells with no sensitivity computed: {missing}"
    return True, f"{len(flagged)} disputed cell(s), all covered by a sensitivity"


def check_sensitivity_survival(sensitivity: pd.DataFrame) -> tuple[bool, str]:
    """Report which results change significance when the source is swapped.

    This never fails the gate. A result that does not survive is a fact about the data,
    not a defect; the point is that it must be visible rather than discovered by a
    reviewer.
    """
    required = {"product", "outcome", "trade_source", "p_value"}
    if sensitivity.empty or not required.issubset(sensitivity.columns):
        return True, "no annual source sensitivity to assess"
    flips: list[str] = []
    keys = ["product", "outcome"]
    for key, group in sensitivity.groupby(keys):
        significant = pd.to_numeric(group["p_value"], errors="coerce").lt(0.05)
        if significant.nunique() > 1:
            flips.append("/".join(str(part) for part in key))
    if flips:
        return True, f"does not survive the source swap, must not be relied on: {sorted(flips)}"
    return True, "every result keeps its significance under the source swap"


def load_table_sources(path: Path) -> dict[str, list[str]]:
    """Load the mapping from report table label to the files behind it."""
    import yaml

    payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("tables"), dict):
        raise ValueError("report_tables.yml must contain a top-level 'tables' mapping")
    return {str(k): [str(v) for v in vs] for k, vs in payload["tables"].items()}


def prose_without_tables(tex: str, checked_labels: set[str] | None = None) -> str:
    """Return the document body with the separately-checked tables removed.

    Only environments whose label is verified against a declared source are dropped,
    because those numbers are already covered. Everything else stays, including any
    table that declares no source.

    Removing every float instead left a hole exactly where stale values collect: the
    claim-evidence matrix is an unlabelled ``longtable``, so it was stripped here and
    absent from the mapped tables, and was checked by nothing at all.
    """
    labels = checked_labels or set()

    def drop(match: re.Match[str]) -> str:
        body = match.group(0)
        found = re.search(r"\\label\{([^{}]+)\}", body)
        if found is not None and found.group(1) in labels:
            return " "
        return body

    return re.sub(r"\\begin\{(table|longtable)\}.*?\\end\{\1\}", drop, tex, flags=re.DOTALL)


#: Numbers written inside math mode, which is how the report states a quantity.
_MATH = re.compile(r"\$([^$]{1,80})\$")


def check_prose_numbers(
    tex: str,
    frames: list[pd.DataFrame],
    *,
    allow: set[float] | None = None,
    checked_labels: set[str] | None = None,
) -> tuple[bool, str]:
    """Every quantity stated in the prose must be reproducible from the bundle.

    Only math-mode spans are read, because that is how the report writes a number it
    is asserting. Values that are stated in words, and years, are left alone. Figures
    that are legitimately derived in the text rather than read from a file, such as a
    half-life computed from an adjustment coefficient, are declared in the allow list
    with a reason recorded beside them in configuration.
    """
    allow = allow or set()
    body = prose_without_tables(tex, checked_labels)
    unmatched: list[float] = []
    for span in _MATH.findall(body):
        cleaned = span.replace("{,}", "").replace("\\%", "")
        for token in _NUMBER.findall(cleaned):
            try:
                value = float(token)
            except ValueError:  # pragma: no cover - regex guarantees a number
                continue
            if 1900.0 <= value <= 2100.0 and value.is_integer():
                continue
            if abs(value) < 1e-9 or value in allow:
                continue
            decimals = len(token.split(".")[1]) if "." in token else 0
            if not _reproducible(value, decimals, frames):
                unmatched.append(value)
    if unmatched:
        shown = sorted(set(unmatched))[:10]
        return False, f"{len(set(unmatched))} prose value(s) not reproducible: {shown}"
    return True, "every quantity stated in the prose reproduces from the bundle"


def claim_matrix_rows(tex: str) -> list[str]:
    """Return the body rows of the claim-evidence matrix.

    The matrix is the one table with no declared source of its own, because each row
    points at wherever in the paper the claim is shown.
    """
    match = re.search(r"\\begin\{longtable\}.*?\\end\{longtable\}", tex, re.DOTALL)
    if match is None:
        return []
    # Everything up to \endhead is the repeating column header rather than a claim.
    # Keeping it would treat a header cell as a row whose numbers need a source.
    body = match.group(0)
    for marker in ("\\endhead", "\\midrule"):
        if marker in body:
            body = body.split(marker, 1)[1]
            break
    rows = []
    for segment in body.split("\\\\"):
        cleaned = re.sub(r"\\(?:top|mid|bottom)rule|\\endhead", " ", segment)
        if cleaned.count("&") >= 2 and "caption" not in cleaned:
            rows.append(cleaned)
    return rows


def check_claim_matrix(
    tex: str,
    table_frames: dict[str, list[pd.DataFrame]],
    fallback: list[pd.DataFrame],
    *,
    allow: set[float] | None = None,
) -> tuple[bool, str]:
    """Verify each matrix row against the source behind the table it cites.

    Every row names where its claim is shown. Checking a row's numbers against the
    whole bundle would accept a figure that appears somewhere, anywhere, which is how
    a stale monthly coefficient survived in the matrix while the table it cited had
    already been corrected. Checking against the cited table's own source does not.

    Rows that cite a section rather than a table fall back to the whole bundle, since
    there is no narrower source to hold them to.
    """
    allow = allow or set()
    bad: list[str] = []
    for row in claim_matrix_rows(tex):
        # A row may cite more than one table, and then its numbers may come from any of
        # them: a claim about the licensed model that names the difference-only figure
        # for comparison is checkable only against both.
        frames = [
            frame
            for label in re.findall(r"\\ref\{(tab:[^{}]+)\}", row)
            for frame in table_frames.get(label, [])
        ]
        if not frames:
            frames = fallback
        claim = _strip_latex(row.split("&")[0])[:44]
        # an en-dashed year range reads as a negative number otherwise: 2013--2020
        for value, decimals in printed_numbers([row.replace("--", " ")]):
            if 1900.0 <= value <= 2100.0 and float(value).is_integer():
                continue
            if abs(value) < 1e-9 or value in allow:
                continue
            if not _reproducible(value, decimals, frames):
                bad.append(f"{claim!r}: {value}")
    if bad:
        return False, f"{len(bad)} matrix value(s) not in the cited source: {bad[:6]}"
    return True, f"all {len(claim_matrix_rows(tex))} claim-matrix rows check out"


def check_bundle_within_window(
    report_inputs: Path,
    *,
    start_year: int,
    end_year: int,
    exempt: set[str] | None = None,
) -> tuple[bool, str]:
    """Does every bundle artifact stay inside the declared study window?

    Sources keep publishing after the window closes, so an artifact that is never
    trimmed quietly gains years the analysis did not use. A reader checking a claim
    against the bundle then sees a longer series than the paper was written from,
    and a range or stability claim can be true of one and false of the other.

    Files that legitimately extend past the window are named in the config with a
    reason, in the same way divergent trade cells are.
    """
    exempt = exempt or set()
    offenders: list[str] = []
    for path in sorted(report_inputs.glob("*.csv")):
        if path.name in exempt:
            continue
        frame = pd.read_csv(path)
        if "year" not in frame.columns:
            continue
        years = pd.to_numeric(frame["year"], errors="coerce").dropna()
        outside = years[(years < start_year) | (years > end_year)]
        if not outside.empty:
            span = (
                f"{int(outside.min())}"
                if outside.nunique() == 1
                else (f"{int(outside.min())}-{int(outside.max())}")
            )
            offenders.append(f"{path.name} ({span})")
    if offenders:
        return False, (f"artifact(s) outside {start_year}-{end_year} and not declared: {offenders}")
    return True, (
        f"every bundle artifact stays within {start_year}-{end_year}; "
        f"{len(exempt)} declared exemption(s)"
    )


#: A statistic quoted in prose, with the comparison it asserts.
_P_VALUE = re.compile(r"p\s*(=|<|>|\\le|\\leq|\\ge|\\geq)\s*\$?\s*(\d*\.\d+|\d+)")
_F_STATISTIC = re.compile(r"F\$?\s*(=)\s*\$?\s*(\d*\.\d+|\d+)")

#: Which columns hold which kind of statistic.
_STATISTIC_COLUMNS: dict[str, Callable[[str], bool]] = {
    "p": lambda name: "p_value" in name or name == "p",
    "F": lambda name: "f_statistic" in name,
}


def _satisfied(operator: str, quoted: float, decimals: int, values: list[float]) -> bool:
    """Does some recorded statistic support the comparison the prose asserts?"""
    tolerance = 0.5 * (10.0**-decimals) + 1e-9
    if operator == "=":
        return any(abs(value - quoted) <= tolerance for value in values)
    if operator in {"<", "\\le", "\\leq"}:
        return any(value <= quoted + tolerance for value in values)
    return any(value >= quoted - tolerance for value in values)


def check_prose_statistics(
    tex: str, frames: list[pd.DataFrame], *, checked_labels: set[str] | None = None
) -> tuple[bool, str]:
    """Check quoted test statistics against columns that hold that kind of statistic.

    ``check_prose_numbers`` accepts any number that appears anywhere in the bundle,
    which is too weak for a statistic. When the price model selection was corrected and
    the diesel cointegration p-value moved from 0.088 to 0.022, the report kept quoting
    0.088 and every gate passed: a Eurostat balance residual and several monthly
    import-dependence ratios sit within half a printed unit of 0.088, so the number was
    reproducible from the bundle while being false about the thing it described.

    A p-value is therefore checked only against columns that hold p-values, and an F
    statistic only against F columns. The comparison is honoured, so ``p<0.001`` asks
    whether some recorded p-value is below the bound rather than equal to it.

    A bound asserted over a set of terms, as in "these terms have p<=0.007", is checked
    for existence rather than for all of them: the prose does not say which terms it
    means in a form this can read.
    """
    body = prose_without_tables(tex, checked_labels)
    pools: dict[str, list[float]] = {kind: [] for kind in _STATISTIC_COLUMNS}
    for frame in frames:
        for column in frame.select_dtypes("number").columns:
            name = str(column).lower()
            for kind, belongs in _STATISTIC_COLUMNS.items():
                if belongs(name):
                    pools[kind].extend(float(v) for v in frame[column].dropna())

    unsupported: list[str] = []
    for kind, pattern in (("p", _P_VALUE), ("F", _F_STATISTIC)):
        if not pools[kind]:
            continue
        for match in pattern.finditer(body):
            operator, token = match.group(1), match.group(2)
            decimals = len(token.split(".")[1]) if "." in token else 0
            if not _satisfied(operator, float(token), decimals, pools[kind]):
                context = body[max(0, match.start() - 48) : match.start()]
                context = " ".join(context.split())[-44:]
                unsupported.append(f"{kind}{operator}{token} (...{context})")

    if unsupported:
        return False, f"{len(unsupported)} quoted statistic(s) not in the bundle: {unsupported[:4]}"
    counted = sum(len(pools[kind]) for kind in pools)
    return True, f"every quoted statistic reproduces from a recorded one ({counted} available)"


#: A sentence has to be about prices before a price coefficient can be read out of it.
_PRICE_CLAIM = re.compile(
    r"elasticity|pass-through|co-movement|error.correction|Spanish|spread|price",
    re.IGNORECASE,
)


def _matches_estimate(value: float, decimals: int, estimates: list[float]) -> bool:
    """Is ``value`` a rounded form of one of these coefficients?

    Unlike :func:`_reproducible` this does not also try the value divided by a hundred.
    That fallback exists because ratios are sometimes printed as percentage points, and
    applying it to coefficients matched a monthly kt figure of 103 against a price
    elasticity of 1.0254.
    """
    tolerance = 0.5 * (10.0**-decimals) + 1e-9
    return any(abs(estimate - value) <= tolerance for estimate in estimates)


def document_sections(tex: str) -> list[tuple[str, str]]:
    """Split the document into (label, body), labelling by the first ``sec:`` label."""
    heading = re.compile(r"\\(?:sub)?section\{")
    starts = [match.start() for match in heading.finditer(tex)]
    sections: list[tuple[str, str]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(tex)
        body = tex[start:end]
        found = re.search(r"\\label\{(sec:[^{}]+)\}", body)
        sections.append((found.group(1) if found else "", body))
    return sections


def check_prose_uses_licensed_models(
    tex: str,
    *,
    licensed_estimates: list[float],
    superseded_estimates: list[float],
    may_cite_superseded: set[str],
) -> tuple[bool, str]:
    """Flag a coefficient quoted from a model family the diagnostics did not licence.

    The price model family is chosen from the data, and correcting that choice changed
    which numbers the paper is entitled to headline. The conclusion went on quoting the
    difference-only diesel elasticity of 0.73 to 1.01 after the licensed model became an
    error-correction model giving 0.713 to 1.242. Every gate passed, because both
    numbers are real: they are estimates from a model that was fitted and persisted,
    just not the one the diagnostics selected.

    A number is flagged when it reproduces from a superseded family's estimates and from
    no licensed estimate. Sections whose subject is a superseded family are exempt by
    name, because reporting what the discarded specification said is the point there.

    Floats are excluded: table values are checked against their declared source, and the
    claim-evidence matrix against the tables each row cites, both of which are stricter.
    """
    body_of = re.compile(r"\\begin\{(table|longtable)\}.*?\\end\{\1\}", re.DOTALL)

    bad: list[str] = []
    for label, section in document_sections(tex):
        if label in may_cite_superseded:
            continue
        prose = body_of.sub(" ", section)
        # Only sentences that are about prices at all. Numeric agreement alone is far
        # too weak a signal: a diesel coverage ratio printed as 0.800 sits within half
        # a printed unit of the gasoline short-run elasticity of 0.7997 and has nothing
        # to do with it.
        for paragraph in prose.split("\n\n"):
            if not _PRICE_CLAIM.search(paragraph):
                continue
            # A superseded figure may be quoted anywhere it is attributed: a paragraph
            # that cross-references the section where that specification is set out is
            # telling the reader which model the number comes from, which is the whole
            # thing this check exists to require.
            cited = set(re.findall(r"\\ref\{(sec:[^{}]+)\}", paragraph))
            if cited & may_cite_superseded:
                continue
            for match in _MATH.finditer(paragraph):
                for token in _NUMBER.findall(match.group(1).replace("{,}", "")):
                    try:
                        value = float(token.replace(",", ""))
                    except ValueError:  # pragma: no cover - regex guarantees a number
                        continue
                    decimals = len(token.split(".")[1]) if "." in token else 0
                    # Compared as coefficients, so without the percentage-point
                    # fallback in _reproducible: a coefficient is never a number a
                    # hundred times smaller.
                    if not _matches_estimate(value, decimals, superseded_estimates):
                        continue
                    if _matches_estimate(value, decimals, licensed_estimates):
                        continue
                    bad.append(f"{value} in {label or 'an unlabelled section'}")
    if bad:
        return False, (
            f"{len(bad)} coefficient(s) quoted from a superseded model family: {bad[:6]}"
        )
    return True, "no claim quotes a model family the diagnostics did not licence"


def load_yaml_block(path: Path, key: str) -> dict[str, Any]:
    """Return one top-level mapping from the report-table config, or an empty dict."""
    import yaml

    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    block = loaded.get(key, {})
    return dict(block) if isinstance(block, dict) else {}
