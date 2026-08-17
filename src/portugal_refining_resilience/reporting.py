from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .io import sha256_file


def build_report_bundle(
    *,
    destination: Path,
    files: list[Path],
    required: bool = True,
) -> dict[str, object]:
    """Copy empirical report inputs and write a checksum manifest."""
    destination.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    missing: list[str] = []
    for source in files:
        if not source.exists():
            missing.append(str(source))
            continue
        target = destination / source.name
        shutil.copy2(source, target)
        entries.append(
            {
                "file": target.name,
                "source_path": str(source),
                "sha256": sha256_file(target),
                "bytes": target.stat().st_size,
            }
        )
    manifest: dict[str, object] = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "files": entries,
        "missing": missing,
        "complete": not missing,
    }
    (destination / "report_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if required and missing:
        raise FileNotFoundError(f"Report bundle incomplete. Missing: {missing}")
    return manifest
