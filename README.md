# multigas

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Python package for processing, analyzing, and visualizing multi-gas volcanic monitoring data.**

Developed through collaboration between CVGHM (Center for Volcanology and Geological Hazard Mitigation) and USGS for Campbell Scientific datalogger systems measuring volcanic gas emissions (CO2, SO2, H2S) and meteorological data.

---

## Installation

### Requirements

- Python 3.11 or higher
- Windows, macOS, or Linux

### Install with uv (recommended)

```bash
# Install uv package manager
pip install uv

# Clone repository
git clone https://github.com/martanto/multigas.git
cd multigas

# Install with all dependencies
uv sync
```

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

### Fluent queries

`MultiGasData` inherits from `Query`, so column selection and inspection
chain directly on the result:

```python
ds.select_numeric_columns().selected_columns
# ['CO2', 'SO2', 'H2S', ...]

ds.select_columns(["CO2", "SO2"]).df.head()

ds.missing_columns   # columns with any NaN / empty value
ds.empty_columns     # columns that are all-NaN, all-zero, or all-empty
ds.refresh()         # restore the pristine DataFrame and clear selection
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
│   ├── io.py            # read_file — one-call convenience wrapper
│   └── exceptions.py    # MultigasException hierarchy (auto-logs on raise)
├── data/
│   └── loader.py        # DataLoader — file I/O, normalisation, joblib cache
└── utils/
    ├── path.py          # ensure_dir helper
    ├── cache.py         # get_cache_key / get_cache_path / save_cache
    ├── validation.py    # check_columns_exist, check_sampling_consistency
    └── dataframe.py     # to_dateime_index, get_dates helpers
```

### Core types (`multigas.core.types`)

| Name | Kind | Description |
|---|---|---|
| `MultiGasData` | `dataclass(Query)` | Wraps a loaded DataFrame with `dataset_type`, `source_path`, `index_col`, and the fluent `Query` API |
| `DatasetType` | `StrEnum` | Sampling intervals as pandas frequency aliases: `ONE_SECOND="1s"`, `TWO_SECONDS="2s"`, `ONE_MINUTE="1min"`, `SIX_HOURS="6h"`, plus categorical modes `ZERO="zero"`, `SPAN="span"`, `WX="wx"` |
| `SensorStatus` | `IntEnum` | Datalogger status codes (e.g. `WARMING_UP=-1`, `SAMPLE_ACQUISITION=1`, `SPAN_CO2_SO2=4`), each with a `.description` property |
| `FileFormat` | `StrEnum` | `CSV`, `EXCEL`, `PARQUET`, `JSON` |
| `LogLevel` | `StrEnum` | `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `DatasetMetadataDict` | `TypedDict` | Optional TOA5 header fields (`station`, `logger_type`, `firmware`, …) |
| `DateLike` | type alias | `str \| datetime \| pd.Timestamp` |
| `ColumnName` | type alias | `str` |
| `Comparator` | type alias | `str` (e.g. `">="`, `"=="`) |

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
