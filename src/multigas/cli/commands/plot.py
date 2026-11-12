"""Render standard multi-gas figures from a CSV file."""

import json
from pathlib import Path

import click
from rich.panel import Panel
from rich.table import Table
from rich.console import Console

from multigas.plot import Plot
from multigas.core.types import DatasetType
from multigas.core.exceptions import MultigasException
from multigas.plot.dimensions import validate_dimension


def _dimension(ctx: click.Context, param: click.Parameter,
               value: float | None) -> float | None:
    """Validate dimensions during Click parsing, preserving the option name."""
    try:
        return validate_dimension(value, param.name or "dimension")
    except ValueError as exc:
        raise click.BadParameter(str(exc), ctx=ctx, param=param) from exc


@click.command(help="Create standard six-hour multi-gas plots from a CSV data file.")
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
@click.option(
    "--one-column",
    is_flag=True,
    help="Stack all ten panels in one column.",
)
@click.option("--verbose", is_flag=True, help="Emit informational loading logs.")
@click.option("--width", type=float, callback=_dimension,
              help="Whole-figure width in millimetres, including titles and captions.")
@click.option("--height", type=float, callback=_dimension,
              help="Whole-figure height in millimetres; overrides automatic height.")
@click.option("--json", "json_output", is_flag=True, help="Print result paths as JSON.")
def legacy_plot(
    input_path: Path,
    dataset_type: str,
    save_as: str,
    output_dir: Path | None,
    start_date: str | None,
    end_date: str | None,
    one_column: bool,
    verbose: bool,
    json_output: bool,
    width: float | None,
    height: float | None,
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
            columns=1 if one_column else 2,
            width=width,
            height=height,
        ).plot_all()
    except (MultigasException, ValueError) as exc:
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


class PlotGroup(click.Group):
    """Route historical path-first arguments to the original plot command."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        """Insert the legacy command unless an explicit subcommand is present."""
        if args and args[0] not in self.commands and args[0] not in {"--help", "-h"}:
            args.insert(0, "standard")
        return super().parse_args(ctx, args)


@click.group(cls=PlotGroup, help="Plot CSV_PATH, or use columns for selected panels.")
def plot() -> None:
    """Dispatch standard or selected-column plotting."""


legacy_plot.hidden = True
plot.add_command(legacy_plot, "standard")


@plot.command("columns")
@click.argument("column_names", nargs=-1, required=True)
@click.option(
    "--source",
    required=True,
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
)
@click.option(
    "--dataset-type",
    required=True,
    type=click.Choice([kind.value for kind in DatasetType], case_sensitive=False),
)
@click.option(
    "--save-as",
    default="PNG",
    show_default=True,
    type=click.Choice(["PNG", "PDF", "HTML"], case_sensitive=False),
)
@click.option("--output-dir", type=click.Path(path_type=Path, file_okay=False))
@click.option("--start-date", help="Inclusive first date or timestamp.")
@click.option(
    "--end-date", help="Inclusive last timestamp; date-only includes all day."
)
@click.option("--one-column", is_flag=True, help="Stack selected panels in one column.")
@click.option("--verbose", is_flag=True, help="Emit informational loading logs.")
@click.option("--width", type=float, callback=_dimension,
              help="Whole-figure width in millimetres, including titles and captions.")
@click.option("--height", type=float, callback=_dimension,
              help="Whole-figure height in millimetres; overrides automatic height.")
@click.option("--json", "json_output", is_flag=True, help="Print figure path as JSON.")
def columns(
    column_names: tuple[str, ...],
    source: Path,
    dataset_type: str,
    save_as: str,
    output_dir: Path | None,
    start_date: str | None,
    end_date: str | None,
    one_column: bool,
    verbose: bool,
    json_output: bool,
    width: float | None,
    height: float | None,
) -> None:
    """Render one time-series panel per COLUMN_NAMES (spaces or commas)."""
    from multigas.plot import plot_columns

    try:
        path = plot_columns(
            source,
            column_names,
            dataset_type,
            save_as,
            output_dir,
            verbose,
            start_date,
            end_date,
            layout_columns=1 if one_column else 2,
            width=width,
            height=height,
        )
    except (MultigasException, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    if json_output:
        click.echo(json.dumps({"figure": str(path)}))
    else:
        Console().print(Panel(str(path), title="Figure complete", expand=False))
