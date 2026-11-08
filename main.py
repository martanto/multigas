"""Import the Tangkuban Parahu 2-second example and plot every observation.

Run ``uv run --extra api main.py``; start the dashboard API with the same storage
root to browse this persistent dataset. No time range or downsampling is applied
unless a date range is explicitly supplied on the command line.
"""

import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(override=False)


EXAMPLE_SOURCE = Path(
    r"D:\Data\Multigas Tangkuban Parahu\TANG_RTU\TANG_RTU_ChemData_Sec2.dat"
)


def await_job(store, job: dict, verbose: bool = True) -> dict:
    """Wait for a local background job and report progress changes."""
    previous = None
    while True:
        current = store.get("jobs", job["id"])
        message = current.get("message", current["status"])
        if verbose and message != previous:
            print(message, flush=True)
            previous = message
        if current["status"] == "complete":
            return current["result"]
        if current["status"] in {"failed", "cancelled", "interrupted"}:
            raise RuntimeError(current.get("error", current["status"]))
        time.sleep(0.2)


def main(
    source: Path | None = None,
    output: Path | None = None,
    normalize: bool = False,
    figure: bool = True,
    start: str | None = None,
    end: str | None = None,
    format: str = "png",
    verbose: bool = True,
) -> dict:
    """Persist the explicit 2s example and export full-resolution scatter panels.

    Args:
        source (Path | None): Source; otherwise environment or the 2s example.
        output (Path | None): Storage; otherwise MULTIGAS_APP_DIR or output/app.
        normalize (bool): Opt in to missing-record, duplicate, and sampling exclusions.
        figure (bool): Export a full-resolution ten-panel scatter figure.
        start (str | None): Explicit inclusive UTC lower bound; all data by default.
        end (str | None): Explicit inclusive UTC upper bound; all data by default.
        format (str): PNG, PDF, or SVG.
        verbose (bool): Print progress.

    Returns:
        dict: Dataset identifier and optional scientific artifact paths.

    Raises:
        RuntimeError: If ingestion or figure generation fails.

    Example:
        >>> result = main(figure=False)
    """
    from multigas.api.schemas import ExportSpec
    from multigas.utils.app_store import AppStore
    from multigas.utils.app_export import export_artifact
    from multigas.utils.app_ingest import ingest
    from multigas.utils.app_example import stage_local_file

    source = (
        source
        if source is not None
        else Path(os.getenv("MULTIGAS_EXAMPLE_SOURCE") or EXAMPLE_SOURCE)
    )
    output = (
        output
        if output is not None
        else Path(os.getenv("MULTIGAS_APP_DIR") or "output/app")
    )
    store = AppStore(output)
    try:
        staged = stage_local_file(store, source)
        spec = {
            "station": staged["preview"]["station"] or "TANG_RTU",
            "timestamp": "TIMESTAMP",
            "mode": "2s",
            "units": {},
            "normalize": normalize,
        }
        result = await_job(
            store,
            store.submit(
                "import",
                {"staged": staged["id"], "import": spec},
                lambda job, work: ingest(store, staged, spec, job, work),
            ),
            verbose,
        )
        if figure:
            export = ExportSpec(
                dataset=result["dataset"],
                kind="figure",
                start=start,
                end=end,
                format=format,
            )
            artifact = await_job(
                store,
                store.submit(
                    "export",
                    export.model_dump(),
                    lambda job, work: export_artifact(store, export, job, work),
                ),
                verbose,
            )
            record = store.get("artifacts", artifact["artifact"])
            result["figure"] = str(
                output / "artifacts" / record["id"] / record["filename"]
            )
            result["manifest"] = str(
                output / "artifacts" / record["id"] / "manifest.json"
            )
        print(result, flush=True)
        return result
    finally:
        store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="Apply recorded normalization exclusions",
    )
    parser.add_argument("--no-figure", action="store_true")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--format", choices=["png", "pdf", "svg"], default="png")
    args = parser.parse_args()
    main(
        args.source,
        args.output,
        args.normalize,
        not args.no_figure,
        args.start,
        args.end,
        args.format,
    )
