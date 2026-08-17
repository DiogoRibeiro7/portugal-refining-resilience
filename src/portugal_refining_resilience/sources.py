from __future__ import annotations

import re
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


def download_file(url: str, destination: Path, *, timeout: int = 120) -> Path:
    """Download a source file without silently overwriting a different payload."""
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL: {url!r}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    destination.write_bytes(response.content)
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
