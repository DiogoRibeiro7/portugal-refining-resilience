from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import ProjectPaths


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
) -> tuple[bool, str]:
    """Validate that a source reconciliation has enough overlap and mostly passes tolerance."""
    if not path.exists():
        return False, f"Missing reconciliation file: {path.name}"
    frame = pd.read_csv(path)
    if "reconciliation_status" not in frame.columns:
        return False, "Missing reconciliation_status column"
    n_rows = len(frame)
    if n_rows < min_rows:
        return False, f"Only {n_rows} overlapping reconciliation rows; need at least {min_rows}"
    within = frame["reconciliation_status"].eq("within_tolerance")
    share = float(within.mean()) if n_rows else 0.0
    if share < min_within_tolerance_share:
        return (
            False,
            f"{share:.1%} within tolerance; need at least {min_within_tolerance_share:.1%}",
        )
    return True, f"{n_rows} rows; {share:.1%} within tolerance"


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
    expected_terms = {"matosinhos_transition", "energy_stress_2022", "post_stress"}
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
    return True, f"Price model choices recorded for {len(choices)} products"


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

    trade_path = paths.processed / "fuel_trade_annual.csv"
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
        paths.metrics / "jodi_trade_annual_completeness.csv",
        paths.metrics / "jodi_demand_annual_completeness.csv",
        paths.metrics / "jodi_refinery_output_annual_completeness.csv",
    ]
    passed, detail = validate_jodi_completeness(completeness_files)
    checks.append(_check_record("jodi_annual_completeness_valid", passed, detail))

    passed, detail = validate_monthly_panel(paths.processed / "fuel_monthly_analytical_panel.csv")
    checks.append(_check_record("monthly_event_panel_valid", passed, detail))

    passed, detail = validate_monthly_event_outputs(paths.metrics)
    checks.append(_check_record("monthly_event_outputs_valid", passed, detail))

    eurostat_panel = paths.processed / "eurostat_physical_balance_panel.csv"
    checks.append(
        _check_record(
            "eurostat_balance_available",
            eurostat_panel.exists(),
            "Required before full petroleum-product balance claims",
        )
    )

    passed, detail = validate_price_outputs(paths.metrics)
    checks.append(_check_record("price_outputs_valid", passed, detail))

    passed, detail = validate_reconciliation(paths.metrics / "jodi_dgeg_trade_reconciliation.csv")
    checks.append(_check_record("dgeg_trade_reconciliation_valid", passed, detail))

    return pd.DataFrame(checks)
