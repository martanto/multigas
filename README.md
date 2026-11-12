# multigas

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Python package for processing, analyzing, and visualizing multi-gas volcanic monitoring data.**

Developed through collaboration between CVGHM (Center for Volcanology and Geological Hazard Mitigation) and USGS for Campbell Scientific datalogger systems measuring volcanic gas emissions (CO2, SO2, H2S) and meteorological data.

The data is inherently **time-series**: every dataset is a stream of gas / calibration / weather readings sampled over time, and every DataFrame flowing through the package is expected to carry a `pd.DatetimeIndex`.

---

## Documentation

Full documentation lives in the [`wiki/`](wiki/) directory — start at
[`wiki/Home.md`](wiki/Home.md).

| Page | Purpose |
|---|---|
| [Home](wiki/Home.md) | Overview, repository map, navigation, glossary |
| [Getting Started](wiki/Getting-Started.md) | Install, first load, fluent queries, wind analysis, dev workflow |
| [API Reference](wiki/API-Reference.md) | Public methods, signatures, and parameter tables |
| [CLI Reference](wiki/CLI-Reference.md) | Command-line commands, source locations, and argument details |
| [Queries](wiki/Queries.md) | Complete `Query` method index with argument types and defaults |
| [Data Columns](wiki/Data-Columns.md) | Per-column dictionary for the datalogger's TOA5 / CSV output — meaning, units, and onboard processing |
| [Wind Analysis](wiki/Wind-Analysis.md) | Sector / quadrant tables, bearing normalisation, `add_wind_direction` / `add_wind_quadrant` contracts |
| [Logging](wiki/Logging.md) | Sink layout, retention, runtime toggles, `ENABLE_LOG` contract |
| [Exceptions](wiki/Exceptions.md) | Hierarchy, auto-log behaviour, soft vs hard failures, catching patterns |
| [Multi-GAS plotting](wiki/Plot.md) | Six-hour and selected-column APIs, CLI, date filters, captions, and exports |

---

## Installation

### Requirements

- Python 3.11 or higher
- Windows, macOS, or Linux
- [`uv`](https://docs.astral.sh/uv/) as the package manager (no `pip install` / `python -m pip`)

### Install with uv (recommended)

```bash
# Install uv package manager (one time, per machine)
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows (PowerShell):
# powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clone repository
git clone https://github.com/martanto/multigas.git
cd multigas

# Install with all dependencies
uv sync
```

`uv sync` creates a virtual environment under `.venv/`. Activate it before
running Python directly (skip if you use `uv run`, which resolves the env
automatically):

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (cmd)
.venv\Scripts\activate.bat
```

Deactivate with `deactivate` when done.

Verify:

```bash
uv run python -c "import multigas; print(multigas.__version__)"
```

Full walkthrough: [`wiki/Getting-Started.md`](wiki/Getting-Started.md).

---

## Quick start

Load a Campbell Scientific TOA5 (or plain CSV) file and get a `MultiGasData`
back — a DataFrame wrapper with fluent column-selection helpers.

```python
from multigas import read_file

ds = read_file("data/site_a.dat", dataset_type="1min")

ds.df.head()               # underlying DataFrame (datetime-indexed)
ds.dataset_type            # <DatasetType.ONE_MINUTE: '1min'>
ds.source_path             # absolute path to the source file
ds.start_date_str          # e.g. '2025-01-01'
ds.end_date_str            # e.g. '2025-01-31'
ds.numeric_columns         # numeric-dtype column names

```

Need full control over paths, cache behaviour, or verbosity? Use `DataLoader`
directly:

```python
from multigas import DataLoader

loader = DataLoader(
    output_dir="output",
    cache_dir="output/cache",
    overwrite=False,
    verbose=True,
)
ds = loader.load("data/site_a.dat", dataset_type="1min")
```

Both entry points serve from an on-disk `joblib` cache keyed by absolute path
plus mtime. Stale or corrupted entries are dropped transparently.

With the default `normalize=True`, loading also replaces `"NAN"` sentinels
with `NaN`, collapses duplicate timestamps (keeping the last row), coerces
numeric columns, and — for sampling-interval datasets (`1s`, `2s`, `1min`,
`6h`) — keeps only rows whose spacing matches the expected interval.

Every parameter is documented in [`wiki/API-Reference.md`](wiki/API-Reference.md).

### Command-line normalization

The `multigas normalize` command provides the same normalized load from a
terminal. It writes `<output-dir>/normalized/<source-stem>.csv`; the default
output root is `./output`.

```bash
uv run multigas normalize data/site_a.dat --dataset-type 1min
uv run multigas normalize data/site_a.dat --dataset-type 1min --json
uv run multigas normalize data/site_a.dat --dataset-type 1min \
  --output-dir results --index-col TIMESTAMP --no-cache
```

Use `uv run multigas --help` or `uv run multigas normalize --help` for the
complete option list. The command requires `--dataset-type` and supports
`--drop-empty-columns`, `--cache-dir`, `--overwrite`, and `--verbose`.
See the [CLI Reference](wiki/CLI-Reference.md) for all arguments, defaults,
types, and source locations.

### Multi-gas plotting

Plot selected numeric columns from any dataset type in one figure:

```bash
uv run multigas plot columns Avg_CO2_lowpass Avg_SO2 \
  --source data/site_a.csv --dataset-type 6h \
  --start-date 2025-01-01 --end-date 2025-03-31
```

Comma-separated names are also accepted; names are trimmed and deduplicated
in order. Missing/nonnumeric names are reported together. Each panel shows
finite observations on a linear time axis, with a wrapped caption below the
figure describing source, dates, exclusions, and relevant gas caveats.
Empty columns display an explicit message. Use `--save-as PNG|PDF|HTML`,
`--one-column`, and optional inclusive date bounds (a date-only end includes
the whole day). Output is `figures/<source-stem>-columns.<extension>` beneath
`--output-dir` (default `./output`); `--json` returns `{"figure": "..."}`.
Python exposes the lazy `multigas.plot.plot_columns(source, column_names,
dataset_type=None, ..., layout_columns=2)` API, also accepting `MultiGasData`.
See [selected-column figures](wiki/Plot.md#selected-column-figures).

Render six-hour datasets into full-period and trailing-three-month figures:

```bash
uv run multigas plot data/site_a.csv --dataset-type 6h
uv run multigas plot data/site_a.csv --dataset-type 6h --one-column
uv run multigas plot data/site_a.csv --dataset-type 6h --save-as PDF
uv run multigas plot data/site_a.csv --dataset-type 6h --save-as HTML --json
uv run multigas plot data/site_a.csv --dataset-type 6h --start-date 2025-01-01 --end-date 2025-03-31
```

Figures are written under `<output-dir>/figures` (default `./output/figures`).
Use `--one-column` to stack all ten panels in one column, or set
`Plot(..., columns=1)` in Python. PNG, PDF, and HTML support this option;
two columns remain the default.

Use `--start-date` and `--end-date` to select an inclusive date range. An empty
range reports an explicit error. The public `multigas.plot.Plot` API also
accepts an already loaded `MultiGasData`.

PNG and vector PDF output use a compact, configurable Nature-inspired panel
layout with distinct, consistently assigned Nature Reviews palette colors,
parenthesized panel labels, and captions directly below the plots. The columns
use a compact gutter and retain outer padding. Choose `--save-as PDF` for editable
vector artwork. Faint dashed major gridlines sit behind the data; units are explained in the
caption. Each panel overlays a gap-aware 7-day rolling median on the recorded
points and reports its valid-reading count. Wide-ranging ratios use log axes,
and far outliers are marked on the axis edge instead of flattening the record.
Grey bands mark logger outages longer than two days, and the caption warns
when the SO2 baseline is at or below zero. PNG and PDF are 280 mm x 190 mm
with two columns (fits A4 landscape with margins), or 280 mm x 380 mm
with `--one-column`. HTML output adds linked zooming and hover values. Gas units are reported as unassigned when the TOA5 units row is
blank; figure captions preserve that limitation. See the [figure guide](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/)
and [artwork palette guidance](https://www.nature.com/documents/natrev-artworkguide.pdf).

### Fluent queries

See the complete [`Query` method reference](wiki/Queries.md) for every
method, argument type, and default.

`MultiGasData` inherits from `Query`, so column selection, filtering, and
inspection chain directly on the result. `Query` mutates its working
DataFrame in place; a pristine copy is kept in `df_original` and
`refresh()` restores it.

```python
ds.select_numeric_columns().selected_columns
# ['CO2', 'SO2', 'H2S', ...]

ds.select_columns(["CO2", "SO2"]).get().head()

ds.missing_columns   # columns with any NaN / empty value
ds.empty_columns     # columns that are all-NaN, all-zero, or all-empty
ds.refresh()         # restore the pristine DataFrame and clear selection
```

Filter rows with `where(column, comparator, value)`. The comparator accepts
any alias from `multigas.core.constant.COMPARATOR` — symbolic (`">="`,
`"!="`), English (`"greater than"`, `"not equal"`), or Indonesian
(`"lebih besar sama dengan"`, `"tidak sama dengan"`). If `column` matches
the index name, the comparison runs against the DatetimeIndex instead of a
column.

```python
(
    ds.where("CO2", ">", 1.0)
      .where("TIMESTAMP", ">=", "2025-01-01")
      .select_columns(["CO2", "SO2"])
      .get()          # narrows ds.df to the selected columns and returns it
)
```

Date and numeric-range helpers use pandas partial-string slicing so both
bounds are inclusive:

```python
ds.where_date("2025-01-15")                       # a single day
ds.where_date_between("2025-01", "2025-02")       # two months, inclusive
ds.where_values_between("CO2", 0.5, 1.5)          # inclusive numeric range
```

`get()` commits the current selection — it replaces `ds.df` with the
column-projected frame and recomputes `numeric_columns`, so dropped
columns only come back via `refresh()`.

### Wind analysis

If the dataset carries a bearings column (in degrees), `MultiGasData` can
attach a sector or quadrant label per row. Bearings are normalised modulo
360; `NaN` bearings produce `None` (no row is dropped).

```python
# Sector label — 4, 8, or 16 sectors
ds.add_wind_direction("WD_deg", as_code=True, direction_to_use=16)

# Quadrant label — 4 or 8 quadrants (default 8)
ds.add_wind_quadrant("WD_deg", as_code=False, quadrant_to_use=8)
```

---

## Development

```bash
# Lint and auto-fix
uv run ruff check --fix src/

# Type check (uses `ty`, not mypy)
uvx ty check src/

# Run all tests
uv run pytest tests/

# Run a single test file
uv run pytest tests/path/to/test_file.py

# Check for circular imports after any module change
uv run pytest tests/test_imports.py -v
```

---

## Package layout

The package uses the `src/` layout. Public entry points are re-exported from
`multigas`:

```
src/multigas/
├── __init__.py          # Exposes read_file, DataLoader, version metadata
├── cli/                 # Click console interface (`multigas normalize`)
├── logging.py           # Loguru logger + enable/disable/level helpers
├── config/              # Configuration (stub)
├── core/
│   ├── __init__.py      # Re-exports DatasetType, enums, type aliases, exceptions
│   ├── types.py         # Enums and type aliases
│   ├── query.py         # Query — fluent column/filter mixin
│   ├── constant.py      # COMPARATOR + WIND_DIRECTIONS_* / WIND_QUADRANTS_*
│   ├── io.py            # read_file — one-call convenience wrapper
│   └── exceptions.py    # MultigasException hierarchy (auto-logs on raise)
├── data/
│   ├── __init__.py      # Re-exports DataLoader, MultiGasData
│   ├── loader.py        # DataLoader — file I/O, normalisation, joblib cache
│   └── multigas_data.py # MultiGasData — DataFrame + provenance wrapper (extends Query)
├── plot/
│   ├── __init__.py      # Lazy Plot, plot_columns and plot_completeness exports
│   ├── columns.py       # Selected-column observation-only PNG / PDF / HTML
│   ├── plot.py          # Standard six-hour plotting API
│   ├── six_hours.py     # Ten-panel styling and renderers
│   └── plot_completeness.py # plot_completeness — daily-completeness PNG from the summary CSV
└── utils/
    ├── path.py          # ensure_dir helper
    ├── cache.py         # get_cache_key / get_cache_path / save_cache / load_cache / clear_cache
    ├── validation.py    # check_columns_exist, validate_dataframe_column, check_sampling_consistency
    └── dataframe.py     # to_datetime_index, get_dates, convert_to_wind_direction, convert_to_wind_quadrant, calculate_completeness, count_csv_rows
```

### Core types (`multigas.core.types`)

| Name | Kind | Description |
|---|---|---|
| `MultiGasData` | class (subclass of `Query`) | Wraps a loaded DataFrame with `dataset_type`, `source_path`, `index_col`, and the fluent `Query` API. Adds `add_wind_direction` / `add_wind_quadrant` for compass-label columns, `to_csv` / `to_excel` for tabular export, and `extract_daily` for per-day CSV splits with completeness stats (also writes `<source_slug>-completeness.csv` next to the daily folder, renders it to `<source_slug>-completeness.png` via `multigas.plot.plot_completeness` unless `plot=False`, and adds `<source_slug>.json` when `return_as_list=True`). Lives in `multigas.data.multigas_data` (re-exported from `multigas.data`) |
| `DatasetType` | `StrEnum` | Sampling intervals as pandas frequency aliases: `ONE_SECOND="1s"`, `TWO_SECONDS="2s"`, `ONE_MINUTE="1min"`, `SIX_HOURS="6h"`, plus categorical modes `ZERO="zero"`, `SPAN="span"`, `WX="wx"`. Exposes `.total_data` (expected records per day for sampling-interval members) and `.label` (hyphenated form such as `"one-minute"`, used as a path segment by `extract_daily`) |
| `SensorStatus` | `IntEnum` | Datalogger status codes (e.g. `WARMING_UP=-1`, `SAMPLE_ACQUISITION=1`, `SPAN_CO2_SO2=4`), each with a `.description` property |
| `FileFormat` | `StrEnum` | `CSV`, `EXCEL`, `PARQUET`, `JSON` |
| `LogLevel` | `StrEnum` | `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `DatasetMetadataDict` | `TypedDict` | Optional TOA5 header fields (`station`, `logger_type`, `firmware`, …) |
| `DateLike` | type alias | `str \| datetime \| pd.Timestamp` |
| `ColumnName` | type alias | `str` |
| `Comparator` | type alias | `str` (e.g. `">="`, `"=="`) |

Full parameter tables for every public callable: [`wiki/API-Reference.md`](wiki/API-Reference.md).

### Exceptions (`multigas.core.exceptions`)

Every subclass auto-logs on construction — do **not** add a manual
`logger.error(...)` before `raise`. Override the class-level `_log_level`
attribute (default `"ERROR"`) to lower severity.

```
MultigasException
├── DatasetError
│   ├── FilterError
│   ├── ColumnError
│   └── DateRangeError
├── ValidationError
├── CacheError
├── LoaderError
├── MetadataError
├── PlotError
└── ConfigError
```

Full per-class raise conditions, catching patterns, and the soft-vs-hard
failure convention: [`wiki/Exceptions.md`](wiki/Exceptions.md).

### Logging (`multigas.logging`)

The package ships a preconfigured `loguru` logger. Handlers are only
registered when the `ENABLE_LOG` environment variable is `"true"` (set it in
`.env` or export it before running).

```python
from multigas.logging import (
    logger,
    enable_logging,
    disable_logging,
    set_log_level,
    set_log_directory,
)

logger.info("hello")           # no-op unless ENABLE_LOG=true
enable_logging()               # register console + file sinks
set_log_level("DEBUG")         # console-only; file sinks stay at DEBUG/ERROR
set_log_directory("./logs")    # rotate to a new directory
disable_logging()              # remove all handlers
```

When enabled, two rotating files are written to `logs/`:

- `multigas_YYYY-MM-DD.log` — `DEBUG+`, 30-day retention, zipped on rotation
- `errors_YYYY-MM-DD.log` — `ERROR+`, 90-day retention, zipped on rotation

Sink formats, the auto-log contract for exceptions, and the
`ENABLE_LOG` worker-inheritance semantics live in
[`wiki/Logging.md`](wiki/Logging.md).

---

## Dependencies

| Package | Purpose |
|---|---|
| `pandas` | DataFrame operations |
| `numpy` | Numerical computing |
| `openpyxl` | Excel file I/O |
| `joblib` | On-disk DataFrame cache |
| `loguru` | Structured logging |
| `python-dotenv` | `.env` loading for `ENABLE_LOG` |
| `python-slugify` | File-name-safe slugs for output paths |
| `click` | Command-line parsing and command registration |
| `rich` | CLI spinner and result summary |
| `matplotlib` | Figure rendering (imported lazily by `multigas.plot`) |
| `bokeh` | Interactive HTML figure rendering by `multigas.plot.Plot` |
| `seaborn` | Scoped plot styling for `plot_completeness` |
| `data-availability` | Daily-completeness chart used by `plot_completeness` |

---

## License

[MIT](LICENSE) — Copyright (c) 2026, Martanto
