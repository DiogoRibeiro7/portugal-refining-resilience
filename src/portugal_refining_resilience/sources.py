from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup


def load_source_manifest(path: Path) -> dict[str, dict[str, str]]:
    """Load and type-check the source manifest."""
    payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("sources.yml must contain a top-level 'sources' mapping")
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("sources.yml must contain a top-level 'sources' mapping")
    return cast("dict[str, dict[str, str]]", sources)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_download_metadata(
    destination: Path,
    *,
    url: str,
    payload_sha256: str,
    status: str,
) -> None:
    metadata = {
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "url": url,
        "sha256": payload_sha256,
        "bytes": destination.stat().st_size,
        "source_vintage_status": status,
    }
    sidecar = destination.with_suffix(destination.suffix + ".metadata.json")
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def download_file(
    url: str,
    destination: Path,
    *,
    timeout: int = 120,
    overwrite: bool = False,
    record_metadata: bool = True,
) -> Path:
    """Download a source file and prevent silent raw-source mutation.

    Existing destinations are preserved by default. If the newly retrieved
    payload differs, callers must pass ``overwrite=True`` intentionally.
    """
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL: {url!r}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.content
    payload_sha256 = _sha256_bytes(payload)
    status = "new_snapshot"
    if destination.exists():
        existing_sha256 = _sha256_bytes(destination.read_bytes())
        if existing_sha256 != payload_sha256 and not overwrite:
            raise FileExistsError(
                f"{destination} already exists with a different SHA-256. "
                "Pass overwrite=True only for an intentional new source vintage."
            )
        status = "unchanged_snapshot" if existing_sha256 == payload_sha256 else "overwritten"
    if not destination.exists() or overwrite:
        destination.write_bytes(payload)
    if record_metadata:
        _write_download_metadata(destination, url=url, payload_sha256=payload_sha256, status=status)
    return destination


def discover_download_links(
    landing_page: str,
    *,
    suffixes: tuple[str, ...] = (".xlsx", ".xls", ".csv", ".zip"),
    timeout: int = 60,
) -> list[str]:
    """Discover downloadable files from a statistical landing page."""
    response = requests.get(landing_page, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"])
        clean = href.lower().split("?")[0]
        if clean.endswith(suffixes):
            links.append(urljoin(landing_page, href))
    return sorted(set(links))


def year_from_url(url: str) -> int | None:
    """Extract a plausible four-digit year from a download URL."""
    matches = re.findall(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)", url)
    return int(matches[-1]) if matches else None
