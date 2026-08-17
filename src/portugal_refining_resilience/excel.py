from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def workbook_inventory(path: Path, *, preview_rows: int = 8) -> pd.DataFrame:
    """Return workbook sheet names, dimensions, and compact previews for source auditing."""
    if not path.exists():
        raise FileNotFoundError(path)
    xls = pd.ExcelFile(path)
    records: list[dict[str, Any]] = []
    for sheet in xls.sheet_names:
        frame = pd.read_excel(path, sheet_name=sheet, header=None)
        preview = frame.head(preview_rows).fillna("").astype(str).to_csv(index=False, header=False)
        records.append(
            {
                "file": path.name,
                "sheet": sheet,
                "rows": int(frame.shape[0]),
                "columns": int(frame.shape[1]),
                "preview": preview[:2000],
            }
        )
    return pd.DataFrame(records)


def normalise_text(value: object) -> str:
    """Normalise labels from Portuguese statistical spreadsheets."""
    return " ".join(str(value).strip().lower().replace("\n", " ").split())
