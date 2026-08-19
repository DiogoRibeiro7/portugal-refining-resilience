from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb"))


def main(*, save_outputs: bool = False) -> None:
    """Execute analytical notebooks in filename order.

    Executed state is discarded by default. The notebooks are committed without
    outputs, and the pipeline's real products are the files it writes under
    ``data/``, ``figures/`` and ``tables/`` rather than notebook display state.
    Saving execution output back would put every run into the diff and invite
    results to be read from notebook prose instead of the persisted evidence.
    """
    for path in NOTEBOOKS:
        print(f"Executing {path.name}", flush=True)
        notebook = nbformat.read(path, as_version=4)
        client = NotebookClient(
            notebook,
            timeout=900,
            kernel_name="python3",
            resources={"metadata": {"path": str(ROOT)}},
        )
        client.execute()
        if save_outputs:
            nbformat.write(notebook, path)


if __name__ == "__main__":
    main(save_outputs="--save-outputs" in sys.argv[1:])
