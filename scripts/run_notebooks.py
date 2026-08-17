from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb"))


def main() -> None:
    """Execute analytical notebooks in filename order and save executed state."""
    for path in NOTEBOOKS:
        print(f"Executing {path.name}")
        notebook = nbformat.read(path, as_version=4)
        client = NotebookClient(
            notebook,
            timeout=900,
            kernel_name="python3",
            resources={"metadata": {"path": str(ROOT)}},
        )
        client.execute()
        nbformat.write(notebook, path)


if __name__ == "__main__":
    main()
