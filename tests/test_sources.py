from pathlib import Path
from typing import Any

import pytest

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
