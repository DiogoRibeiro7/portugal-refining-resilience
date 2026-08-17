from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


def sha256_file(path: Path) -> str:
    """Return a SHA-256 checksum for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def persist_dataframe(
    df: pd.DataFrame,
    csv_path: Path,
    *,
    key_columns: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    write_parquet: bool = True,
) -> dict[str, Any]:
    """Persist a dataframe and a small machine-readable provenance sidecar.

    CSV is mandatory for auditability. Parquet is additionally written when requested.
    Duplicate keys are rejected when ``key_columns`` are supplied.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")
    if key_columns:
        missing = [column for column in key_columns if column not in df.columns]
        if missing:
            raise ValueError(f"Missing key columns: {missing}")
        duplicated = df.duplicated(key_columns, keep=False)
        if duplicated.any():
            examples = df.loc[duplicated, key_columns].head(10).to_dict("records")
            raise ValueError(f"Duplicate keys detected: {examples}")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)

    parquet_path: Path | None = None
    if write_parquet:
        parquet_path = csv_path.with_suffix(".parquet")
        df.to_parquet(parquet_path, index=False)

    sidecar = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "rows": int(len(df)),
        "columns": list(df.columns),
        "csv": str(csv_path),
        "csv_sha256": sha256_file(csv_path),
        "parquet": str(parquet_path) if parquet_path else None,
        "metadata": metadata or {},
    }
    sidecar_path = csv_path.with_suffix(".metadata.json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2, default=str) + "\n", encoding="utf-8")
    return sidecar


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write an indented UTF-8 JSON document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
