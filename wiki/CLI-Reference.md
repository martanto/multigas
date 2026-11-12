# CLI Reference

Command-line interface registered by the `multigas` package. Install the
package, then run commands with `uv run multigas ...`.

> Back to [Home](Home.md) · See also [Getting Started](Getting-Started.md).

## CLI index

| Name                 | Description                                                                             | File location                                                                         | Argument details                             |
|----------------------|-----------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|----------------------------------------------|
| `multigas`           | Root command group; provides version reporting and command discovery.                   | [`src/multigas/cli/main.py`](../src/multigas/cli/main.py)                             | [Root options](#multigas)                    |
| `multigas normalize` | Load and normalize an input data file, then write a normalized CSV and print a summary. | [`src/multigas/cli/commands/normalize.py`](../src/multigas/cli/commands/normalize.py) | [Arguments and options](#multigas-normalize) |

## `multigas`

Run the root command to see available commands, or request the installed
package version:

```bash
uv run multigas --help
uv run multigas --version
```

| Argument / option | Type | Default | Description                                  |
|-------------------|------|---------|----------------------------------------------|
| `--help`          | flag | —       | Show help and exit.                          |
| `--version`       | flag | —       | Show the installed package version and exit. |

## `multigas normalize`

Run `normalize` with a source file and its sampling interval. The first
example prints the default summary table; the second prints JSON:

```bash
uv run multigas normalize data/site_a.dat --dataset-type 1min
uv run multigas normalize data/site_a.dat --dataset-type 1min --json
```

Writes `<output-dir>/normalized/<source-stem>.csv`. If `--output-dir` is not
provided, the output root is `<cwd>/output`. The command reports the input,
output path, row and column counts, and dataset type as a Rich table by
default. Pass `--json` to print those same fields as a JSON object instead.
The JSON keys are `input`, `normalized_csv`, `rows`, `columns`, and
`dataset_type`.

| Argument / option      | Type                                                   | Default                         | Description                                                     |
|------------------------|--------------------------------------------------------|---------------------------------|-----------------------------------------------------------------|
| `INPUT_PATH`           | existing file path                                     | required                        | Source CSV or TOA5 data file. Directories are not accepted.     |
| `--dataset-type`       | choice: `1s`, `2s`, `6h`, `1min`, `zero`, `span`, `wx` | required                        | Sampling interval or acquisition mode used to load the dataset. |
| `--output-dir`         | directory path                                         | `None` (→ `<cwd>/output`)       | Root directory for normalized output.                           |
| `--index-col`          | string                                                 | `TIMESTAMP`                     | Timestamp column to promote to the datetime index.              |
| `--drop-empty-columns` | flag (`bool`)                                          | `False`                         | Drop columns that are entirely empty during normalization.      |
| `--no-cache`           | flag (`bool`)                                          | `False`                         | Disable cache reads and writes.                                 |
| `--cache-dir`          | directory path                                         | `None` (→ `<output-dir>/cache`) | Directory for cache entries.                                    |
| `--overwrite`          | flag (`bool`)                                          | `False`                         | Reload even when a cache entry exists.                          |
| `--verbose`            | flag (`bool`)                                          | `False`                         | Emit informational loading logs.                                |
| `--json`               | flag (`bool`)                                          | `False`                         | Print the summary as JSON instead of a Rich table.               |
