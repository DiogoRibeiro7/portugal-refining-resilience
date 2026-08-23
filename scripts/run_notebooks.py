"""Execute the analytical notebooks in filename order.

Executed state is discarded by default. The notebooks are committed without outputs, and the
pipeline's real products are the files it writes under ``data/``, ``figures/`` and ``tables/``
rather than notebook display state. Saving execution output back would put every run into the
diff and invite results to be read from notebook prose instead of the persisted evidence.

Three properties matter more than they look.

Unrecognised arguments are refused rather than ignored. The earlier version treated any
argument it did not know as "run everything", so a mistyped flag silently discarded outputs and
``--help`` re-downloaded from five live sources for ten minutes.

Abbreviations are refused too, via ``allow_abbrev=False``. Argparse accepts any unambiguous
prefix of a long option by default, which means ``--save-output`` and even ``--sa`` would
silently mean ``--save-outputs`` and rewrite all twenty-two notebooks with execution state that
this project deliberately does not commit. Refusing unknown flags is worth little if a typo can
still land on the destructive one.

The run prints a closing count, because a run that stops early can still exit zero: a kernel
connection dropped mid-pipeline once and the process reported success after twelve of twenty-two
notebooks. The exit code alone cannot tell a full run from a truncated one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = ROOT / "notebooks"
CELL_TIMEOUT_SECONDS = 900


def select(selection: str | None = None) -> list[Path]:
    """Notebooks to execute, in filename order.

    ``selection`` is a comma-separated list of numeric prefixes, so ``--only 19,20`` rebuilds
    the evidence bundle and reruns the gate without re-downloading the sources.

    A number selects every notebook carrying it, and two notebooks are numbered 14, so
    ``--only 14`` runs both. They run in filename order, the same order a full run uses.
    """
    everything = sorted(NOTEBOOK_DIR.glob("[0-9][0-9]_*.ipynb"))
    if selection is None:
        return everything

    wanted = [part.strip().zfill(2) for part in selection.split(",") if part.strip()]
    if not wanted:
        raise ValueError("--only was given no notebook numbers")

    chosen = [path for path in everything if path.name[:2] in wanted]
    missing = sorted(set(wanted) - {path.name[:2] for path in chosen})
    if missing:
        raise ValueError("no notebook numbered " + ", ".join(missing))
    return chosen


def run(paths: list[Path], *, save_outputs: bool = False) -> None:
    """Execute each notebook, then report how many finished."""
    for position, path in enumerate(paths, start=1):
        print(f"[{position}/{len(paths)}] executing {path.name}", flush=True)
        notebook = nbformat.read(path, as_version=4)
        client = NotebookClient(
            notebook,
            timeout=CELL_TIMEOUT_SECONDS,
            kernel_name="python3",
            resources={"metadata": {"path": str(ROOT)}},
        )
        client.execute()
        if save_outputs:
            nbformat.write(notebook, path)

    print(f"completed {len(paths)} of {len(paths)} notebooks", flush=True)


def build_parser() -> argparse.ArgumentParser:
    """The command line, kept separate so it can be tested without executing anything."""
    parser = argparse.ArgumentParser(
        prog="run_notebooks",
        description="Execute the analytical notebooks in filename order.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--save-outputs",
        action="store_true",
        help="write executed state back into the notebooks (off by default)",
    )
    parser.add_argument(
        "--only",
        metavar="NN[,NN...]",
        help=(
            "run just these notebooks by number, e.g. --only 19,20 to rebuild the evidence "
            "bundle and rerun the gate. A number selects every notebook carrying it, and two "
            "are numbered 14"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        paths = select(args.only)
    except ValueError as error:
        parser.error(str(error))

    run(paths, save_outputs=args.save_outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
