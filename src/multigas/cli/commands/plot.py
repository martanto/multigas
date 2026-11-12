"""Render standard multi-gas figures from a CSV file."""

import json
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table
from rich.console import Console

from multigas.plot import Plot
from multigas.core.exceptions import DatasetError


@click.command(
    help="Create standard six-hour multi-gas plots from a CSV data file."
)
@click.argument(
    "input_path", type=click.Path(path_type=Path, exists=True, dir_okay=False)
)
@click.option(
    "--dataset-type",
    required=True,
    type=click.Choice(["6h"], case_sensitive=False),
    help="Dataset type (the six-hour layout supports 6h).",
)
@click.option(
    "--save-as",
    default="PNG",
    show_default=True,
    type=click.Choice(["PNG", "PDF", "HTML"], case_sensitive=False),
)
@click.option(
    "--output-dir", type=click.Path(path_type=Path, file_okay=False), default=None
)
@click.option(
    "--start-date",
    type=str,
    default=None,
    help="Inclusive first date to plot (YYYY-MM-DD).",
)
@click.option(
    "--end-date",
    type=str,
    default=None,
    help="Inclusive last date to plot (YYYY-MM-DD).",
)
@click.option("--verbose", is_flag=True, help="Emit informational loading logs.")
@click.option("--json", "json_output", is_flag=True, help="Print result paths as JSON.")
def plot(
    input_path: Path,
    dataset_type: str,
    save_as: str,
    output_dir: Path | None,
    start_date: str | None,
    end_date: str | None,
    verbose: bool,
    json_output: bool,
) -> None:
    """Plot INPUT_PATH as full-period and trailing-three-month figures."""
    try:
        outputs = Plot(
            input_path,
            dataset_type,
            save_as,
            output_dir,
            verbose=verbose,
            start_date=start_date,
            end_date=end_date,
        ).plot_all()
    except DatasetError as exc:
        raise click.ClickException(str(exc)) from exc
    result = {name: str(path) for name, path in outputs.items()}
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold")
    table.add_column()
    for name, path in result.items():
        table.add_row(name.replace("_", " ").title(), path)
    Console().print(Panel(table, title="Plots complete", expand=False))
