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
| [Data Columns](wiki/Data-Columns.md) | Per-column dictionary for the datalogger's TOA5 / CSV output — meaning, units, and onboard processing |
| [Wind Analysis](wiki/Wind-Analysis.md) | Sector / quadrant tables, bearing normalisation, `add_wind_direction` / `add_wind_quadrant` contracts |
| [Logging](wiki/Logging.md) | Sink layout, retention, runtime toggles, `ENABLE_LOG` contract |
| [Exceptions](wiki/Exceptions.md) | Hierarchy, auto-log behaviour, soft vs hard failures, catching patterns |

---

## Installation

### Requirements

- Python 3.11 or higher
- Windows, macOS, or Linux
- [`uv`](https://docs.astral.sh/uv/) as the package manager (no `pip install` / `python -m pip`)

### Install with uv (recommended)

```bash
# Install uv package manager (one time, per machine)
pip install uv

# Clone repository
git clone https://github.com/martanto/multigas.git
cd multigas

# Install with all dependencies
uv sync
```

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

Every parameter is documented in [`wiki/API-Reference.md`](wiki/API-Reference.md).

### Fluent queries

`MultiGasData` inherits from `Query`, so column selection, filtering, and
inspection chain directly on the result. `Query` mutates its working
DataFrame in place; a pristine copy is kept in `df_original` and
`refresh()` restores it.

```python
ds.select_numeric_columns().selected_columns
# ['CO2', 'SO2', 'H2S', ...]

ds.select_columns(["CO2", "SO2"]).df.head()

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
├── logging.py           # Loguru logger + enable/disable/level helpers
├── config/              # Configuration (stub)
├── core/
│   ├── __init__.py      # Re-exports MultiGasData, DatasetType, exceptions
│   ├── types.py         # Enums, type aliases, MultiGasData dataclass
│   ├── query.py         # Query — fluent column/filter mixin
│   ├── constant.py      # COMPARATOR + WIND_DIRECTIONS_* / WIND_QUADRANTS_*
│   ├── io.py            # read_file — one-call convenience wrapper
│   └── exceptions.py    # MultigasException hierarchy (auto-logs on raise)
├── data/
│   └── loader.py        # DataLoader — file I/O, normalisation, joblib cache
└── utils/
    ├── path.py          # ensure_dir helper
    ├── cache.py         # get_cache_key / get_cache_path / save_cache / clear_cache
    ├── validation.py    # check_columns_exist, validate_dataframe_column, check_sampling_consistency
    └── dataframe.py     # to_datetime_index, get_dates, convert_to_wind_direction, convert_to_wind_quadrant
```

### Core types (`multigas.core.types`)

| Name | Kind | Description |
|---|---|---|
| `MultiGasData` | `dataclass(Query)` | Wraps a loaded DataFrame with `dataset_type`, `source_path`, `index_col`, and the fluent `Query` API. Adds `add_wind_direction` / `add_wind_quadrant` for compass-label columns |
| `DatasetType` | `StrEnum` | Sampling intervals as pandas frequency aliases: `ONE_SECOND="1s"`, `TWO_SECONDS="2s"`, `ONE_MINUTE="1min"`, `SIX_HOURS="6h"`, plus categorical modes `ZERO="zero"`, `SPAN="span"`, `WX="wx"` |
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

---

## License

[MIT](LICENSE) — Copyright (c) 2026, Martanto
