from __future__ import annotations

import hashlib
import json
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

try:  # pragma: no cover - depends on the optional parquet engine
    from pyarrow.lib import ArrowException as pa_error
except ImportError:  # pragma: no cover
    pa_error = ValueError


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

    # CSV is the mandatory audit artifact and is already on disk. Parquet is a typed
    # convenience, so a column pyarrow cannot encode is recorded rather than allowed to
    # abort a pipeline run and leave the outputs half written.
    parquet_path: Path | None = None
    parquet_error: str | None = None
    if write_parquet:
        candidate = csv_path.with_suffix(".parquet")
        try:
            df.to_parquet(candidate, index=False)
        except (ValueError, TypeError, ImportError, pa_error) as error:
            parquet_error = f"{type(error).__name__}: {error}"
            warnings.warn(
                f"Parquet not written for {csv_path.name}: {parquet_error}",
                RuntimeWarning,
                stacklevel=2,
            )
        else:
            parquet_path = candidate

    sidecar = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "rows": int(len(df)),
        "columns": list(df.columns),
        "csv": str(csv_path),
        "csv_sha256": sha256_file(csv_path),
        "parquet": str(parquet_path) if parquet_path else None,
        "parquet_error": parquet_error,
        "metadata": metadata or {},
    }
    sidecar_path = csv_path.with_suffix(".metadata.json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2, default=str) + "\n", encoding="utf-8")
    return sidecar


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write an indented UTF-8 JSON document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
