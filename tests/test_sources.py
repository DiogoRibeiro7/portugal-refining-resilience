from pathlib import Path
from typing import Any

import pytest
import requests
from dataexcept import DataLoadingError, FileWriteError

from portugal_refining_resilience.sources import download_file


class _Response:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


def _fake_get_factory(content: bytes) -> Any:
    def fake_get(url: str, timeout: int) -> _Response:
        assert url == "https://example.test/source.csv"
        assert timeout == 120
        return _Response(content)

    return fake_get


def test_download_file_rejects_silent_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "source.csv"
    destination.write_bytes(b"old")
    monkeypatch.setattr(
        "portugal_refining_resilience.sources.requests.get", _fake_get_factory(b"new")
    )

    with pytest.raises(FileExistsError):
        download_file("https://example.test/source.csv", destination)
    assert destination.read_bytes() == b"old"


def test_download_file_records_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = tmp_path / "source.csv"
    monkeypatch.setattr(
        "portugal_refining_resilience.sources.requests.get", _fake_get_factory(b"new")
    )

    download_file("https://example.test/source.csv", destination)

    assert destination.read_bytes() == b"new"
    metadata = destination.with_suffix(".csv.metadata.json")
    assert metadata.exists()


def test_download_network_failure_retains_url_and_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/source.csv"
    cause = requests.Timeout("timed out")

    def fail_get(*args: object, **kwargs: object) -> None:
        raise cause

    monkeypatch.setattr("portugal_refining_resilience.sources.requests.get", fail_get)
    with pytest.raises(DataLoadingError) as caught:
        download_file(url, tmp_path / "source.csv")

    assert caught.value.source == url
    assert caught.value.original is cause
    assert caught.value.__cause__ is cause


def test_download_write_failure_retains_destination_and_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "source.csv"
    cause = OSError("disk full")
    monkeypatch.setattr(
        "portugal_refining_resilience.sources.requests.get", _fake_get_factory(b"new")
    )

    def fail_write(self: Path, data: bytes) -> int:
        raise cause

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    with pytest.raises(FileWriteError) as caught:
        download_file("https://example.test/source.csv", path)

    assert caught.value.path == str(path)
    assert caught.value.__cause__ is cause
