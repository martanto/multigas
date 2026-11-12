"""Normalize a source data file from the command line."""

import json
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table
from rich.console import Console

from multigas import read_file
from multigas.core.types import DatasetType


@click.command(
    help="Load a multi-gas data file, normalize its records, and write a normalized CSV."
)
@click.argument("input_path", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option(
    "--dataset-type",
    "dataset_type",
    type=click.Choice([member.value for member in DatasetType]),
    required=True,
    help="Sampling interval or acquisition mode.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Root output directory (default: ./output).",
)
@click.option(
    "--index-col", default="TIMESTAMP", show_default=True, help="Timestamp column to index."
)
@click.option("--drop-empty-columns", is_flag=True, help="Drop columns that are entirely empty.")
@click.option("--no-cache", is_flag=True, help="Disable reading and writing the cache.")
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Cache directory (default: <output-dir>/cache).",
)
@click.option("--overwrite", is_flag=True, help="Reload even when a cache entry exists.")
@click.option("--verbose", is_flag=True, help="Emit informational loading logs.")
@click.option("--json", "json_output", is_flag=True, help="Print the summary as JSON.")
def normalize(
    input_path: Path,
    dataset_type: str,
    output_dir: Path | None,
    index_col: str,
    drop_empty_columns: bool,
    no_cache: bool,
    cache_dir: Path | None,
    overwrite: bool,
    verbose: bool,
    json_output: bool,
) -> None:
    """Normalize INPUT_PATH and write a normalized CSV copy."""
    console = Console()
    with console.status("Loading and normalizing data…", spinner="dots"):
        dataset = read_file(
            input_path,
            dataset_type=dataset_type,
            index_col=index_col,
            drop_empty_columns=drop_empty_columns,
            use_cache=not no_cache,
            output_dir=output_dir,
            cache_dir=cache_dir,
            overwrite=overwrite,
            verbose=verbose,
        )

    resolved_output_dir = Path.cwd() / "output" if output_dir is None else output_dir
    normalized_path = resolved_output_dir / "normalized" / f"{input_path.stem}.csv"
    if (
        not normalized_path.exists()
        or normalized_path.stat().st_mtime_ns < input_path.stat().st_mtime_ns
    ):
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.df.to_csv(normalized_path)

    result = {
        "input": str(dataset.source_path),
        "normalized_csv": str(normalized_path),
        "rows": len(dataset.df),
        "columns": len(dataset.df.columns),
        "dataset_type": dataset.dataset_type.value,
    }
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    summary = Table.grid(padding=(0, 1))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Input", result["input"])
    summary.add_row("Normalized CSV", result["normalized_csv"])
    summary.add_row("Rows", f"{len(dataset.df):,}")
    summary.add_row("Columns", f"{len(dataset.df.columns):,}")
    summary.add_row("Dataset type", result["dataset_type"])
    console.print(Panel(summary, title="Normalization complete", expand=False))
