@AGENTS.md

## CLI Architecture

The `multigas` console script is registered in `pyproject.toml` and resolves
to `multigas.cli.main:cli`. The Click command group registers commands from
`multigas.cli.commands`; `normalize` wraps the public `read_file` API and
reports its normalized CSV output and dataset summary with Rich by default,
with an optional `--json` flag for machine-readable output.
