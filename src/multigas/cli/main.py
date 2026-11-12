"""Command-line interface for multigas."""

import click

from multigas.cli.commands.plot import plot
from multigas.cli.commands.normalize import normalize


@click.group()
@click.version_option(package_name="multigas")
def cli() -> None:
    """Process multi-gas monitoring data from the command line."""


cli.add_command(normalize)
cli.add_command(plot)
