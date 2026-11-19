"""Extract normalized multi-gas observations into daily CSV files."""

import json
from typing import cast
from pathlib import Path
from datetime import datetime

import click
import pandas as pd
from rich.panel import Panel
from rich.table import Table
from rich.console import Console

from multigas import read_file
from multigas.core.exceptions import MultigasException
from multigas.utils.dataframe import select_date_range


EXTRACT_DATASET_TYPES = ("1s", "2s", "1min", "6h", "zero")


@click.command(
    help="Normalize a multi-gas source and extract one CSV per calendar day."
)
@click.argument(
    "input_path", type=click.Path(path_type=Path, exists=True, dir_okay=False)
)
@click.option(
    "--dataset-type",
    required=True,
    type=click.Choice(EXTRACT_DATASET_TYPES, case_sensitive=False),
    help="Sampling interval or zero-calibration mode.",
)
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Inclusive first date to extract (YYYY-MM-DD).",
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Inclusive last date to extract (YYYY-MM-DD).",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Root output directory (default: ./output).",
)
@click.option(
    "--index-col", default="TIMESTAMP", show_default=True, help="Timestamp column."
)
@click.option("--verbose", is_flag=True, help="Emit informational processing logs.")
@click.option("--json", "json_output", is_flag=True, help="Print the summary as JSON.")
def extract(
    input_path: Path,
    dataset_type: str,
    start_date: datetime | None,
    end_date: datetime | None,
    output_dir: Path | None,
    index_col: str,
    verbose: bool,
    json_output: bool,
) -> None:
    """Normalize INPUT_PATH and extract its observations by calendar day."""
    console = Console()
    root = Path.cwd() / "output" if output_dir is None else output_dir
    start = start_date.date().isoformat() if start_date is not None else None
    end = end_date.date().isoformat() if end_date is not None else None

    try:
        with console.status("Loading and normalizing data…", spinner="dots"):
            dataset = read_file(
                input_path,
                dataset_type=dataset_type,
                index_col=index_col,
                normalize=True,
                output_dir=root,
                verbose=verbose,
            )
    except (MultigasException, ValueError, OSError) as exc:
        raise click.ClickException(f"Could not load input: {exc}") from exc

    try:
        if start is not None or end is not None:
            dataset.df = select_date_range(dataset.df, start, end)
    except (MultigasException, ValueError, TypeError) as exc:
        raise click.ClickException(f"Could not select dates: {exc}") from exc

    effective_start = dataset.df.index.min().strftime("%Y-%m-%d")
    effective_end = dataset.df.index.max().strftime("%Y-%m-%d")

    try:
        with console.status("Extracting daily files…", spinner="dots"):
            summary = cast(pd.DataFrame, dataset.extract_daily(root))
    except Exception as exc:
        raise click.ClickException(f"Could not extract daily files: {exc}") from exc

    daily_dir = root / "daily" / dataset.dataset_type.label / dataset.basename_slug
    completeness_csv = (
        root
        / "daily"
        / dataset.dataset_type.label
        / f"{dataset.basename_slug}-completeness.csv"
    )
    result = {
        "input": str(dataset.source_path),
        "dataset_type": dataset.dataset_type.value,
        "start_date": effective_start,
        "end_date": effective_end,
        "extracted_days": len(summary),
        "extracted_records": int(summary["total_data"].sum()),
        "daily_directory": str(daily_dir),
        "completeness_csv": str(completeness_csv),
    }

    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Input", result["input"])
    table.add_row("Dataset type", result["dataset_type"])
    table.add_row("Effective dates", f"{effective_start} to {effective_end}")
    table.add_row("Extracted days", f"{result['extracted_days']:,}")
    table.add_row("Extracted records", f"{result['extracted_records']:,}")
    table.add_row("Daily directory", result["daily_directory"])
    table.add_row("Completeness CSV", result["completeness_csv"])
    console.print(Panel(table, title="Daily extraction complete", expand=False))
