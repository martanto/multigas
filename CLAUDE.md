@AGENTS.md

## CLI Architecture

The `multigas` console script is registered in `pyproject.toml` and resolves
to `multigas.cli.main:cli`. The Click command group registers commands from
`multigas.cli.commands`; `normalize` wraps the public `read_file` API and
reports its normalized CSV output and dataset summary with Rich by default,
with an optional `--json` flag for machine-readable output.

The six-hour `Plot` API accepts `columns=1` for ten vertically stacked panels
or `columns=2` (default) for five rows. CLI `--one-column` selects the stacked
layout for PNG, PDF, and HTML, for both output periods. Static figures are
280 x 190 mm by default and 280 x 380 mm with one column.
