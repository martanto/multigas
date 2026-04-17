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

## Development

```bash
# Lint and auto-fix
uv run ruff check --fix src/

# Type check
uvx ty check src/

# Run all tests
uv run pytest tests/

# Run a single test file
uv run pytest tests/path/to/test_file.py

# Check for circular imports
uv run pytest tests/test_imports.py -v
```

---

## Package Structure

```
src/multigas/
├── __init__.py          # Version metadata
├── config/
│   └── logging.py       # Logging setup (console + optional file handler)
└── core/
    ├── exceptions.py    # Custom exception hierarchy
    └── types.py         # Shared type aliases, enums, and TypedDicts
```

### Core types (`multigas.core.types`)

| Name | Kind | Description |
|---|---|---|
| `DateLike` | type alias | `str \| datetime \| pd.Timestamp` |
| `ColumnName` | type alias | `str` |
| `DatasetType` | `StrEnum` | Dataset sampling intervals: `ONE_SECOND`, `TWO_SECONDS`, `ONE_MINUTE`, `SIX_HOURS`, `ZERO`, `SPAN`, `WX` |
| `DatasetMetadataDict` | `TypedDict` | Station metadata from datalogger files |
| `LogLevel` | `StrEnum` | `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `FileFormat` | `StrEnum` | `CSV`, `EXCEL`, `PARQUET`, `JSON` |

### Exceptions (`multigas.core.exceptions`)

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

### Logging (`multigas.config.logging`)

```python
from multigas.config.logging import setup_logging, get_logger
from multigas.core.types import LogLevel

# Basic setup (console only)
logger = setup_logging(LogLevel.INFO)

# Enable file logging to logs/YYYY-MM-DD.log
logger = setup_logging(LogLevel.DEBUG, enable_file_log=True)

# Or set ENABLE_LOG=true in .env to enable file logging automatically
logger = setup_logging()

# Get a named child logger
logger = get_logger("multigas.reader")
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `pandas` | DataFrame operations |
| `numpy` | Numerical computing |
| `openpyxl` | Excel file I/O |
| `loguru` | Structured logging |
| `python-dotenv` | Environment variable loading |

---

## License

[MIT](LICENSE) — Copyright (c) 2026, Martanto
