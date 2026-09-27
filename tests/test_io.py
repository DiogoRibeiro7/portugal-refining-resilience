"""Tests for the persistence layer.

Every auditability claim in this repository rests on these functions: the SHA-256
sidecars, the duplicate-key rejection and the CSV that is written whatever else fails.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from dataexcept import FileReadError, FileWriteError

from portugal_refining_resilience.io import (
    persist_dataframe,
    read_bytes,
    sha256_file,
    write_json,
)


def test_sha256_file_matches_hashlib(tmp_path: Path) -> None:
    path = tmp_path / "payload.bin"
    payload = b"portugal-refining-resilience" * 100_000  # spans the read chunk
    path.write_bytes(payload)

    assert sha256_file(path) == hashlib.sha256(payload).hexdigest()


def test_persist_dataframe_writes_csv_and_sidecar(tmp_path: Path) -> None:
    frame = pd.DataFrame({"year": [2021, 2022], "product": ["diesel"] * 2, "value_kt": [1.0, 2.0]})
    csv_path = tmp_path / "panel.csv"

    sidecar = persist_dataframe(frame, csv_path, key_columns=["year", "product"])

    assert csv_path.exists()
    assert sidecar["rows"] == 2
    assert sidecar["columns"] == ["year", "product", "value_kt"]
    assert sidecar["csv_sha256"] == sha256_file(csv_path)

    written = json.loads((tmp_path / "panel.metadata.json").read_text(encoding="utf-8"))
    assert written["csv_sha256"] == sidecar["csv_sha256"]
    assert written["rows"] == 2


def test_persist_dataframe_rejects_duplicate_keys(tmp_path: Path) -> None:
    """A duplicated key silently doubles a series when the table is later summed."""
    frame = pd.DataFrame({"year": [2021, 2021], "product": ["diesel"] * 2, "value_kt": [1.0, 2.0]})

    with pytest.raises(ValueError, match="Duplicate keys detected"):
        persist_dataframe(frame, tmp_path / "panel.csv", key_columns=["year", "product"])


def test_persist_dataframe_rejects_missing_key_columns(tmp_path: Path) -> None:
    frame = pd.DataFrame({"year": [2021]})

    with pytest.raises(ValueError, match="Missing key columns"):
        persist_dataframe(frame, tmp_path / "panel.csv", key_columns=["year", "product"])


def test_persist_dataframe_records_metadata(tmp_path: Path) -> None:
    frame = pd.DataFrame({"year": [2021], "value_kt": [1.0]})

    persist_dataframe(frame, tmp_path / "panel.csv", metadata={"unit": "kt", "source": "JODI"})

    written = json.loads((tmp_path / "panel.metadata.json").read_text(encoding="utf-8"))
    assert written["metadata"] == {"unit": "kt", "source": "JODI"}


def test_persist_dataframe_keeps_the_csv_when_parquet_fails(tmp_path: Path) -> None:
    """The CSV is the mandatory audit artifact; parquet is a typed convenience.

    A column pyarrow cannot encode must not abort a pipeline run after the CSV has
    already been written, or the outputs are left half produced.
    """
    frame = pd.DataFrame({"year": [2021, 2022], "causal": [False, "conditional"]})
    csv_path = tmp_path / "design.csv"

    with pytest.warns(RuntimeWarning, match="Parquet not written"):
        sidecar = persist_dataframe(frame, csv_path, write_parquet=True)

    assert csv_path.exists()
    assert sidecar["parquet"] is None
    assert sidecar["parquet_error"]
    assert not (tmp_path / "design.parquet").exists()


def test_persist_dataframe_writes_parquet_when_it_can(tmp_path: Path) -> None:
    frame = pd.DataFrame({"year": [2021, 2022], "value_kt": [1.0, 2.0]})

    sidecar = persist_dataframe(frame, tmp_path / "panel.csv", write_parquet=True)

    assert sidecar["parquet_error"] is None
    assert (tmp_path / "panel.parquet").exists()
    assert pd.read_parquet(tmp_path / "panel.parquet").equals(frame)


def test_persist_dataframe_rejects_a_non_dataframe(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="must be a pandas DataFrame"):
        persist_dataframe({"year": [2021]}, tmp_path / "panel.csv")  # type: ignore[arg-type]


def test_write_json_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deeper" / "payload.json"

    write_json(target, {"complete": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"complete": True}


def test_read_failure_retains_path_and_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.csv"
    cause = PermissionError("cannot read source")

    def fail_read(self: Path) -> bytes:
        raise cause

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(FileReadError) as caught:
        read_bytes(path)

    assert caught.value.path == str(path)
    assert caught.value.original is cause
    assert caught.value.__cause__ is cause


def test_csv_write_failure_retains_path_and_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "panel.csv"
    frame = pd.DataFrame({"year": [2024]})
    cause = OSError("disk full")

    def fail_csv(*args: object, **kwargs: object) -> None:
        raise cause

    monkeypatch.setattr(frame, "to_csv", fail_csv)
    with pytest.raises(FileWriteError) as caught:
        persist_dataframe(frame, path, write_parquet=False)

    assert caught.value.path == str(path)
    assert caught.value.original is cause
    assert caught.value.__cause__ is cause


def test_parquet_filesystem_failure_is_not_suppressed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "panel.csv"
    frame = pd.DataFrame({"year": [2024]})
    cause = OSError("disk full")

    def fail_parquet(*args: object, **kwargs: object) -> None:
        raise cause

    monkeypatch.setattr(frame, "to_parquet", fail_parquet)
    with pytest.raises(FileWriteError) as caught:
        persist_dataframe(frame, path)

    assert path.exists()  # The mandatory CSV was written before optional Parquet.
    assert caught.value.path == str(path.with_suffix(".parquet"))
    assert caught.value.__cause__ is cause


def test_json_write_failure_retains_path_and_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "results.json"
    cause = PermissionError("read-only directory")

    def fail_write(self: Path, *args: object, **kwargs: object) -> None:
        raise cause

    monkeypatch.setattr(Path, "write_text", fail_write)
    with pytest.raises(FileWriteError) as caught:
        write_json(path, {"complete": True})

    assert caught.value.path == str(path)
    assert caught.value.__cause__ is cause
