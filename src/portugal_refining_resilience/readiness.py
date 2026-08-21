from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .claims import (
    check_bundle_within_window,
    check_claim_matrix,
    check_event_interval,
    check_flagged_cells_have_sensitivity,
    check_prose_numbers,
    check_prose_statistics,
    check_prose_uses_licensed_models,
    check_quantities_are_checkable,
    check_sensitivity_survival,
    check_stated_sample_sizes,
    load_table_sources,
    load_yaml_block,
    parse_latex_tables,
    verify_table_values,
)
from .config import ProjectPaths, load_analysis_config
from .events import EVENT_PHASES


def _bundle_first(paths: ProjectPaths, working: Path) -> Path:
    """Prefer the bundled copy of a file over the working copy.

    Report-writing prompts read ``artifacts/report_inputs/``. Validating the working
    file instead would certify a table that is not the one the report was written
    from, which is the opposite of what a checksum-protected bundle is for. The
    working path is used only when the file has not been bundled yet.
    """
    bundled = paths.report_inputs / working.name
    return bundled if bundled.exists() else working


def _check_record(check: str, passed: bool, detail: str) -> dict[str, object]:
    return {"check": check, "passed": bool(passed), "detail": detail}


def validate_jodi_completeness(
    files: list[Path], *, start_year: int = 2005, end_year: int = 2024
) -> tuple[bool, str]:
    """Validate that annual JODI diagnostic files contain complete 12-month years."""
    missing_files = [path.name for path in files if not path.exists()]
    if missing_files:
        return False, f"Missing completeness files: {missing_files}"
    required = {"year", "n_months", "complete_year"}
    failures: list[str] = []
    for path in files:
        frame = pd.read_csv(path)
        missing_columns = required - set(frame.columns)
        if missing_columns:
            failures.append(f"{path.name} missing columns {sorted(missing_columns)}")
            continue
        window = frame.loc[frame["year"].between(start_year, end_year)].copy()
        if window.empty:
            failures.append(f"{path.name} has no rows in {start_year}-{end_year}")
            continue
        complete = window["complete_year"].astype(str).str.lower().isin({"true", "1", "yes"})
        incomplete = window.loc[(window["n_months"] != 12) | (~complete)]
        if not incomplete.empty:
            examples = incomplete[["year", "n_months", "complete_year"]].head(5).to_dict("records")
            failures.append(f"{path.name} incomplete examples: {examples}")
    if failures:
        return False, " | ".join(failures)
    return True, f"All JODI completeness rows in {start_year}-{end_year} have 12 months"


def validate_reconciliation(
    path: Path,
    *,
    min_rows: int = 20,
    min_within_tolerance_share: float = 0.9,
    accepted_divergences: list[dict[str, Any]] | None = None,
) -> tuple[bool, str]:
    """Validate a source reconciliation: enough overlap, and no unexplained divergence.

    Two conditions apply. Every out-of-tolerance row must be named in
    ``accepted_divergences`` with the reason it is accepted, so a new data vintage
    cannot quietly widen the gap between sources however few cells it touches. And
    ``min_within_tolerance_share`` of all rows must agree *without* invoking an
    exception, so the exception list cannot grow until it carries the comparison.
    """
    if not path.exists():
        return False, f"Missing reconciliation file: {path.name}"
    frame = pd.read_csv(path)
    required = {"reconciliation_status", "year", "product", "flow"}
    missing = required - set(frame.columns)
    if missing:
        return False, f"Reconciliation file missing columns: {sorted(missing)}"
    n_rows = len(frame)
    if n_rows < min_rows:
        return False, f"Only {n_rows} overlapping reconciliation rows; need at least {min_rows}"

    accepted_keys = {
        (int(entry["year"]), str(entry["product"]), str(entry["flow"]))
        for entry in (accepted_divergences or [])
    }
    keys = list(
        zip(
            frame["year"].astype(int),
            frame["product"].astype(str),
            frame["flow"].astype(str),
            strict=True,
        )
    )
    is_accepted = pd.Series([key in accepted_keys for key in keys], index=frame.index)
    flagged = frame["reconciliation_status"].ne("within_tolerance")

    unexplained = frame.loc[flagged & ~is_accepted, ["year", "product", "flow"]]
    if not unexplained.empty:
        examples = unexplained.head(5).to_dict("records")
        return (
            False,
            f"{len(unexplained)} unexplained divergence(s); justify each in "
            f"config/analysis.yml source_reconciliation.accepted_divergences: {examples}",
        )

    stale = sorted(accepted_keys - {key for key, bad in zip(keys, flagged, strict=True) if bad})

    # Measured over every row, counting a justified divergence as a divergence. This
    # bounds the escape hatch: without it, listing enough exceptions would let two
    # sources that broadly disagree pass a check whose whole purpose is to detect
    # exactly that. The named-exception rule above stops silent drift; this stops the
    # exception list growing until it carries the comparison.
    share = float(frame["reconciliation_status"].eq("within_tolerance").mean())
    if share < min_within_tolerance_share:
        return (
            False,
            f"only {share:.1%} of rows agree without invoking an exception; "
            f"need at least {min_within_tolerance_share:.1%}",
        )
    detail = (
        f"{n_rows} rows; {share:.1%} agree outright; "
        f"{int(is_accepted.sum())} justified divergence(s)"
    )
    if stale:
        detail += f"; {len(stale)} accepted entr(y/ies) no longer diverge: {stale[:3]}"
    return True, detail


def validate_monthly_panel(path: Path) -> tuple[bool, str]:
    """Validate monthly event-panel coverage and phase labeling."""
    if not path.exists():
        return False, f"Missing monthly panel: {path.name}"
    frame = pd.read_csv(path)
    required = {"date", "product", "event_phase"}
    missing = required - set(frame.columns)
    if missing:
        return False, f"Monthly panel missing columns: {sorted(missing)}"
    expected_phases = {
        "pre_matosinhos_closure",
        "matosinhos_transition",
        "energy_stress_2022",
        "post_stress",
    }
    phases = set(frame["event_phase"].dropna().astype(str))
    missing_phases = sorted(expected_phases - phases)
    if missing_phases:
        return False, f"Monthly panel missing event phases: {missing_phases}"
    duplicates = frame.duplicated(["date", "product"], keep=False)
    if duplicates.any():
        examples = frame.loc[duplicates, ["date", "product"]].head(5).to_dict("records")
        return False, f"Duplicate monthly panel keys: {examples}"
    return True, f"Monthly panel covers phases: {sorted(phases)}"


def validate_monthly_event_outputs(metrics_dir: Path) -> tuple[bool, str]:
    """Validate persisted monthly event-study summaries and model coefficients."""
    summary_path = metrics_dir / "monthly_event_phase_summary.csv"
    models_path = metrics_dir / "monthly_event_models.csv"
    missing = [path.name for path in (summary_path, models_path) if not path.exists()]
    if missing:
        return False, f"Missing monthly event outputs: {missing}"

    summary = pd.read_csv(summary_path)
    summary_required = {
        "product",
        "outcome",
        "event_phase",
        "n_months",
        "mean_value",
        "std_value",
    }
    missing_summary = summary_required - set(summary.columns)
    if missing_summary:
        return False, f"monthly_event_phase_summary.csv missing columns: {sorted(missing_summary)}"
    if summary.empty:
        return False, "monthly_event_phase_summary.csv has no rows"

    models = pd.read_csv(models_path)
    model_required = {"product", "outcome", "term", "estimate", "std_error", "p_value", "n_obs"}
    missing_models = model_required - set(models.columns)
    if missing_models:
        return False, f"monthly_event_models.csv missing columns: {sorted(missing_models)}"
    # Both terms are required: the phase indicator alone is the level shift at the
    # boundary only when the phase trend is also reported, so a bundle carrying just
    # the indicators invites it to be quoted as the whole effect.
    expected_terms = set(EVENT_PHASES) | {f"{phase}_trend" for phase in EVENT_PHASES}
    terms = set(models["term"].dropna().astype(str))
    missing_terms = sorted(expected_terms - terms)
    if missing_terms:
        return False, f"monthly_event_models.csv missing phase terms: {missing_terms}"
    return True, f"Monthly event models recorded for {models['outcome'].nunique()} outcomes"


def validate_price_outputs(metrics_dir: Path) -> tuple[bool, str]:
    """Validate that price diagnostics exist and model choice has been recorded."""
    stationarity = metrics_dir / "price_stationarity_diagnostics.csv"
    model_choice = metrics_dir / "price_model_choice.csv"
    missing = [path.name for path in (stationarity, model_choice) if not path.exists()]
    if missing:
        return False, f"Missing price diagnostics: {missing}"
    choices = pd.read_csv(model_choice)
    required = {"product", "model_family", "reason"}
    missing_columns = required - set(choices.columns)
    if missing_columns:
        return False, f"price_model_choice.csv missing columns: {sorted(missing_columns)}"
    if choices.empty:
        return False, "price_model_choice.csv has no rows"

    # A levels regression on weekly fuel prices is only admissible when the
    # diagnostics say so, so the coefficient table must carry that verdict rather
    # than leaving a report writer to assume it.
    models_path = metrics_dir / "price_comovement_models.csv"
    if models_path.exists():
        models = pd.read_csv(models_path)
        verdict_columns = {"model_family", "levels_model_valid"}
        missing_verdict = verdict_columns - set(models.columns)
        if missing_verdict:
            return (
                False,
                f"price_comovement_models.csv missing model-choice verdict columns: "
                f"{sorted(missing_verdict)}",
            )
        unverdicted = models.loc[models["model_family"].isna(), "product"].unique()
        if len(unverdicted):
            return False, f"price_comovement_models.csv rows without a verdict: {list(unverdicted)}"

    families = sorted(set(choices["model_family"].dropna().astype(str)))
    return True, f"Price model choices recorded for {len(choices)} products: {families}"


def build_readiness_checks(
    paths: ProjectPaths, *, manifest_path: Path | None = None
) -> pd.DataFrame:
    """Build tested report-readiness checks from persisted artifacts."""
    manifest_file = manifest_path or paths.report_inputs / "report_manifest.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        bundle_complete = bool(manifest.get("complete"))
        bundle_detail = str(manifest.get("missing", []))
    else:
        bundle_complete = False
        bundle_detail = f"Missing {manifest_file}"

    checks: list[dict[str, object]] = [
        _check_record("core_report_bundle_complete", bundle_complete, bundle_detail)
    ]

    trade_path = _bundle_first(paths, paths.processed / "fuel_trade_annual.csv")
    if trade_path.exists():
        trade = pd.read_csv(trade_path)
        seed_only = "status" in trade.columns and set(trade["status"].dropna()) == {
            "seed_provisional"
        }
        checks.append(
            _check_record(
                "trade_not_seed_only",
                not seed_only,
                "Re-run JODI/DGEG acquisition before publication"
                if seed_only
                else "downloaded/cross-checked trade available",
            )
        )
    else:
        checks.append(_check_record("trade_not_seed_only", False, "Missing fuel_trade_annual.csv"))

    completeness_files = [
        _bundle_first(paths, paths.metrics / name)
        for name in (
            "jodi_trade_annual_completeness.csv",
            "jodi_demand_annual_completeness.csv",
            "jodi_refinery_output_annual_completeness.csv",
        )
    ]
    # JODI starts later than the annual window, so completeness is asserted over the
    # years JODI actually covers rather than over years it cannot have.
    try:
        analysis = load_analysis_config(paths.root)
        jodi_start = int(analysis.get("monthly_start_year", analysis["start_year"]))
        jodi_end = int(analysis["end_year"])
    except (FileNotFoundError, KeyError, ValueError):
        jodi_start, jodi_end = 2005, 2024
    passed, detail = validate_jodi_completeness(
        completeness_files, start_year=jodi_start, end_year=jodi_end
    )
    checks.append(_check_record("jodi_annual_completeness_valid", passed, detail))

    passed, detail = validate_monthly_panel(
        _bundle_first(paths, paths.processed / "fuel_monthly_analytical_panel.csv")
    )
    checks.append(_check_record("monthly_event_panel_valid", passed, detail))

    # These validators take a directory, so point them at the bundle once it exists.
    evidence_dir = paths.report_inputs if paths.report_inputs.exists() else paths.metrics
    passed, detail = validate_monthly_event_outputs(evidence_dir)
    checks.append(_check_record("monthly_event_outputs_valid", passed, detail))

    eurostat_panel = _bundle_first(paths, paths.processed / "eurostat_physical_balance_panel.csv")
    checks.append(
        _check_record(
            "eurostat_balance_available",
            eurostat_panel.exists(),
            "Required before full petroleum-product balance claims",
        )
    )

    passed, detail = validate_price_outputs(evidence_dir)
    checks.append(_check_record("price_outputs_valid", passed, detail))

    reconciliation_config: dict[str, Any] = {}
    try:
        reconciliation_config = dict(
            load_analysis_config(paths.root).get("source_reconciliation", {}) or {}
        )
    except (FileNotFoundError, ValueError):
        reconciliation_config = {}
    accepted = reconciliation_config.get("accepted_divergences") or []
    share = float(reconciliation_config.get("min_within_tolerance_share", 0.9))
    passed, detail = validate_reconciliation(
        _bundle_first(paths, paths.metrics / "jodi_dgeg_trade_reconciliation.csv"),
        min_within_tolerance_share=share,
        accepted_divergences=list(accepted),
    )
    checks.append(_check_record("dgeg_trade_reconciliation_valid", passed, detail))

    return pd.DataFrame(checks)


def _read_if_present(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def build_report_claim_checks(
    paths: ProjectPaths,
    *,
    report_path: Path | None = None,
    table_sources_path: Path | None = None,
) -> pd.DataFrame:
    """Check that the written report agrees with the bundle it draws on.

    The readiness checks establish that the evidence is present and consistent. These
    establish that the report used it: that printed table values are reproducible from
    the file each table is declared to come from, that stated sample sizes match the
    fitted models, that an interval stated in words matches the configured event dates,
    and that no disputed trade cell was quoted without a sensitivity being computed.
    """
    report = report_path or paths.root / "reports" / "report_final.tex"
    mapping_path = table_sources_path or paths.root / "config" / "report_tables.yml"
    checks: list[dict[str, object]] = []

    if not report.exists():
        return pd.DataFrame([_check_record("report_present", False, f"Missing {report.name}")])
    tex = report.read_text(encoding="utf-8")

    # 1. every printed table value must be reproducible from its declared source
    if mapping_path.exists():
        sources = load_table_sources(mapping_path)
        tables = parse_latex_tables(tex)
        unverifiable: list[str] = []
        mismatched: list[str] = []
        for label, files in sources.items():
            rows = tables.get(label)
            if rows is None:
                unverifiable.append(label)
                continue
            frames = [_read_if_present(paths.report_inputs / name) for name in files]
            frames = [frame for frame in frames if not frame.empty]
            if not frames:
                unverifiable.append(label)
                continue
            unmatched = verify_table_values(label, rows, frames)
            if unmatched:
                mismatched.append(f"{label}: {sorted(set(unmatched))[:6]}")
        if mismatched:
            detail = "; ".join(mismatched)
        elif unverifiable:
            detail = f"all mapped tables verified; not checkable: {sorted(unverifiable)}"
        else:
            detail = f"all {len(sources)} mapped tables reproduce from the bundle"
        checks.append(_check_record("report_tables_match_bundle", not mismatched, detail))
    else:
        checks.append(
            _check_record("report_tables_match_bundle", False, f"Missing {mapping_path.name}")
        )

    # 2. sample sizes quoted in the prose
    model_frames = [
        _read_if_present(paths.report_inputs / name)
        for name in (
            "monthly_event_models.csv",
            "annual_interrupted_trend_models.csv",
            "price_short_run_models.csv",
            "price_ecm_models.csv",
        )
    ]
    passed, detail = check_stated_sample_sizes(tex, model_frames)
    checks.append(_check_record("report_sample_sizes_match", passed, detail))

    # 3. an interval stated in words
    try:
        analysis = load_analysis_config(paths.root)
        event_dates = dict(analysis.get("event_dates", {}) or {})
    except (FileNotFoundError, ValueError):
        event_dates = {}
    passed, detail = check_event_interval(tex, event_dates)
    checks.append(_check_record("report_event_interval_correct", passed, detail))

    # 4. disputed cells must have had a sensitivity computed
    reconciliation = _read_if_present(paths.report_inputs / "jodi_dgeg_trade_reconciliation.csv")
    sensitivities = [
        _read_if_present(paths.report_inputs / "stress_2022_source_sensitivity.csv"),
        _read_if_present(paths.report_inputs / "annual_source_sensitivity.csv"),
    ]
    if reconciliation.empty:
        checks.append(
            _check_record("disputed_cells_have_sensitivity", False, "reconciliation absent")
        )
    else:
        passed, detail = check_flagged_cells_have_sensitivity(reconciliation, sensitivities)
        checks.append(_check_record("disputed_cells_have_sensitivity", passed, detail))

    # 5. numbers stated in the prose, including the claim-evidence matrix
    every_frame = [_read_if_present(path) for path in sorted(paths.report_inputs.glob("*.csv"))]
    every_frame = [frame for frame in every_frame if not frame.empty]
    allow: set[float] = set()
    if mapping_path.exists():
        import yaml

        payload = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
        allow = {float(v) for v in (payload.get("prose_allow") or {})}
    # Tables verified against a declared source are excluded; everything else,
    # including the unlabelled claim-evidence matrix, is checked here.
    checked_labels = set(load_table_sources(mapping_path)) if mapping_path.exists() else set()
    passed, detail = check_prose_numbers(
        tex, every_frame, allow=allow, checked_labels=checked_labels
    )
    checks.append(_check_record("report_prose_matches_bundle", passed, detail))

    # 5b. a quoted statistic must reproduce from a column of that kind of statistic
    passed, detail = check_prose_statistics(tex, every_frame, checked_labels=checked_labels)
    checks.append(_check_record("prose_statistics_match_bundle", passed, detail))

    # 5c. a quantity written outside math mode escapes every check above
    passed, detail = check_quantities_are_checkable(tex, checked_labels=checked_labels, allow=allow)
    checks.append(_check_record("quantities_written_where_checked", passed, detail))

    # 6. the claim-evidence matrix, row by row against each cited table's source
    table_frames: dict[str, list[pd.DataFrame]] = {}
    if mapping_path.exists():
        for label, files in load_table_sources(mapping_path).items():
            loaded = [_read_if_present(paths.report_inputs / name) for name in files]
            loaded = [frame for frame in loaded if not frame.empty]
            if loaded:
                table_frames[label] = loaded
    passed, detail = check_claim_matrix(tex, table_frames, every_frame, allow=allow)
    checks.append(_check_record("claim_matrix_matches_cited_source", passed, detail))

    # 7. surface results that change significance when the source is swapped
    passed, detail = check_sensitivity_survival(
        _read_if_present(paths.report_inputs / "annual_source_sensitivity.csv")
    )
    checks.append(_check_record("source_swap_survival_reported", passed, detail))

    # 8. no artifact may cover years the study window excludes unless it says so
    config = load_analysis_config(paths.root)
    scope = config.get("window_scope", {}) or {}
    exempt = {str(entry["file"]) for entry in scope.get("exempt", []) if "file" in entry}
    passed, detail = check_bundle_within_window(
        paths.report_inputs,
        start_year=int(config["start_year"]),
        end_year=int(config["end_year"]),
        exempt=exempt,
    )
    checks.append(_check_record("bundle_within_study_window", passed, detail))

    # 9. a claim must quote the model family the diagnostics licensed for it
    scope = load_yaml_block(mapping_path, "model_family_scope")
    if scope:
        choice = _read_if_present(paths.report_inputs / str(scope["choice_file"]))
        family_files = dict(scope["family_files"])
        chosen = set(choice["model_family"].astype(str)) if not choice.empty else set()
        licensed_files = {family_files[name] for name in chosen if name in family_files}
        superseded_files = set(family_files.values()) - licensed_files

        def _estimates(names: set[str]) -> list[float]:
            values: list[float] = []
            for name in sorted(names):
                frame = _read_if_present(paths.report_inputs / name)
                if "estimate" in frame.columns:
                    values.extend(float(v) for v in frame["estimate"].dropna())
            return values

        passed, detail = check_prose_uses_licensed_models(
            tex,
            licensed_estimates=_estimates(licensed_files),
            superseded_estimates=_estimates(superseded_files),
            may_cite_superseded=set(scope.get("may_cite_superseded", [])),
        )
        checks.append(_check_record("prose_uses_licensed_model_family", passed, detail))

    return pd.DataFrame(checks)
