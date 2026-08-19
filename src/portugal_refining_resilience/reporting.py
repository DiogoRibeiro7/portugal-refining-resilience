from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .io import sha256_file

MANIFEST_NAME = "report_manifest.json"


def build_report_bundle(
    *,
    destination: Path,
    files: list[Path],
    figures: list[Path] | None = None,
    required: bool = True,
) -> dict[str, object]:
    """Copy empirical report inputs and write a checksum manifest.

    Figures are copied and checksummed like any other file but recorded with ``kind``
    set to ``figure``, so a report-writing prompt can tell an image from a
    machine-readable table without the bundle carrying files the manifest does not
    describe. Anything already in the destination that this call did not write is
    removed: a checksum manifest that does not account for every file in the directory
    cannot establish what the report was written from.
    """
    destination.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    missing: list[str] = []
    written: set[str] = {MANIFEST_NAME}

    for kind, sources in (("data", files), ("figure", figures or [])):
        for source in sources:
            if not source.exists():
                missing.append(str(source))
                continue
            target = destination / source.name
            shutil.copy2(source, target)
            written.add(target.name)
            entries.append(
                {
                    "file": target.name,
                    "kind": kind,
                    "source_path": str(source),
                    "sha256": sha256_file(target),
                    "bytes": target.stat().st_size,
                }
            )

    stale = sorted(
        path.name
        for path in destination.iterdir()
        if path.is_file() and path.name not in written and not path.name.startswith(".")
    )
    for name in stale:
        (destination / name).unlink()

    manifest: dict[str, object] = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "files": entries,
        "missing": missing,
        "removed_unmanifested": stale,
        "complete": not missing,
    }
    (destination / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if required and missing:
        raise FileNotFoundError(f"Report bundle incomplete. Missing: {missing}")
    return manifest
