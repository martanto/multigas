@AGENTS.md

## CLI Architecture

`plot` is a Click group dispatcher: historical `plot CSV_PATH` invocations
route to the standard six-hour command; `plot columns COLUMN_NAMES...`
requires `--source` and `--dataset-type` and supports every dataset type.
It wraps lazily exported `multigas.plot.plot_columns` in `plot/columns.py`.
Paths use normalized loading without cache and retain empty columns; loaded
`MultiGasData` is used directly. Selection validates all names together,
rejects nonnumeric columns, slices inclusive dates and filters nonfinite
values. Renderers use an adaptive one/two-column grid with observations only,
linear full-range axes, shared time axes and a below-figure caption. No
six-hour smoothing, clipping or outage rules apply. One PNG/PDF/HTML figure
replaces `figures/<source-stem>-columns.<extension>`; JSON has a `figure` key.

The `multigas` console script is registered in `pyproject.toml` and resolves
to `multigas.cli.main:cli`. The Click command group registers commands from
`multigas.cli.commands`; `normalize` wraps the public `read_file` API and
`plot` wraps the public `multigas.plot.Plot` API for six-hour datasets. Both
commands report results with Rich by default and support `--json` output.
The plot command accepts inclusive `--start-date` / `--end-date` bounds and
reports an explicit error when the selected interval contains no records.
Plot output supports PNG, vector PDF, and Bokeh HTML; all renderers use the
same ten-panel ordering with configurable `columns=1` or `columns=2`
(default). CLI `--one-column` selects `columns=1`. All formats preserve the
panel color mapping, date windows, and below-figure caption. `multigas.plot.six_hours` holds the layout: the pure
helpers `trend` (gap-aware 7-day rolling median), `y_axis` (log scale for
wide positive ratios plus robust limits), `gaps` (record outages longer
than two days), `caption`, and `log_ticks` are shared by the
matplotlib (`_render_static`) and Bokeh (`_render_html`) renderers.

## Documentation (Wiki)

The `wiki/` directory is the documentation source of truth. Add every new
page to its navigation table and to the README documentation index.

| Page | Purpose |
|---|---|
| [Home](wiki/Home.md) | Wiki navigation, repository map, architecture, and glossary |
| [Getting Started](wiki/Getting-Started.md) | Installation, loading, queries, and development workflow |
| [API Reference](wiki/API-Reference.md) | Public API signatures and parameters |
| [CLI Reference](wiki/CLI-Reference.md) | CLI commands and arguments |
| [Queries](wiki/Queries.md) | Query methods and defaults |
| [Data Columns](wiki/Data-Columns.md) | Logger column meanings, units, and processing |
| [Wind Analysis](wiki/Wind-Analysis.md) | Wind sector and quadrant behavior |
| [Logging](wiki/Logging.md) | Logging sinks, retention, and controls |
| [Exceptions](wiki/Exceptions.md) | Exception hierarchy and handling patterns |
| [Multi-GAS plotting](wiki/Plot.md) | Six-hour and selected-column APIs, CLI, date filters, captions, and exports |

The six-hour `Plot` API accepts `columns=1` for ten vertically stacked panels
or `columns=2` (default) for five rows. CLI `--one-column` selects the stacked
layout for PNG, PDF, and HTML, for both output periods. Static figures are
280 x 190 mm by default and 280 x 380 mm with one column.

`Plot` and `plot_columns` append optional `width=None` and `height=None` in millimetres
for the whole figure, including titles and captions. Both plotting CLI commands
expose `--width` / `--height`. Dimensions
are independent: omitted values retain format/layout defaults, explicit height
overrides automatic height. Shared backend-free `plot/dimensions.py` helpers
validate finite positive real values (rejecting booleans). Invalid arguments
raise `ValueError`; undersized layouts raise `PlotError` during rendering.
Static custom exports use
`mm / 25.4` inches without tight cropping; HTML uses
`round(mm * 96 / 25.4)` CSS pixels for the outer canvas and budgets room for
titles, toolbar and reflowed captions. Keep fonts/DPI unchanged and reject
layouts that cannot fit rather than enlarging the requested canvas.
