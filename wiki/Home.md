# multigas — Wiki

Living single-source-of-truth documentation for the `multigas` package.

`multigas` is an early-stage Python package for processing and analyzing
multi-gas volcanic monitoring data (CO2, SO2, H2S) from Campbell Scientific
dataloggers. Every dataset flowing through the package is inherently
**time-series** and is expected to carry a `pd.DatetimeIndex`.

---

## Navigation

| Page | Purpose |
|---|---|
| [Home](Home.md) | Overview, repository map, navigation, glossary |
| [Getting Started](Getting-Started.md) | Install, first load, fluent queries, wind analysis, dev workflow |
| [API Reference](API-Reference.md) | Public methods, signatures, and parameter tables |
| [Logging](Logging.md) | Sink layout, retention, runtime toggles, `ENABLE_LOG` contract |
| [Exceptions](Exceptions.md) | Hierarchy, auto-log behaviour, soft vs hard failures, catching patterns |

> Additional pages (e.g. `Data-Loading.md`, `Query-API.md`,
> `Wind-Analysis.md`, `Caching.md`, `Contributing.md`) will be added
> as the packages / project are completed. Add new pages here as rows
> in the table above so this index stays the single navigation entry
> point.

---

## Repository Map

```
multigas/
├── src/multigas/                # Package (src layout)
│   ├── __init__.py              # Public exports: read_file, DataLoader, version
│   ├── logging.py               # Preconfigured loguru logger + toggles
│   ├── config/                  # Configuration (stub)
│   ├── core/
│   │   ├── __init__.py          # Re-exports MultiGasData, DatasetType, exceptions
│   │   ├── types.py             # Enums, aliases, MultiGasData dataclass
│   │   ├── query.py             # Query — fluent column/filter mixin
│   │   ├── constant.py          # COMPARATOR + WIND_DIRECTIONS_* / WIND_QUADRANTS_*
│   │   ├── io.py                # read_file — one-call convenience wrapper
│   │   └── exceptions.py        # MultigasException hierarchy (auto-logs on raise)
│   ├── data/
│   │   ├── __init__.py          # Re-exports DataLoader
│   │   └── loader.py            # DataLoader — file I/O, normalisation, joblib cache
│   └── utils/
│       ├── __init__.py          # Docstring-only; import helpers directly
│       ├── path.py              # ensure_dir
│       ├── cache.py             # get_cache_key / get_cache_path / save_cache / clear_cache
│       ├── validation.py        # check_columns_exist, validate_dataframe_column, check_sampling_consistency
│       └── dataframe.py         # to_datetime_index, get_dates, convert_to_wind_*
├── tests/                       # Pytest suite (and where all test output belongs)
├── wiki/                        # This documentation
├── changelogs/                  # Daily task log (git-ignored, local only)
├── pyproject.toml               # Project metadata, deps, uv build config
├── ruff.toml                    # Lint config (rules E, W, F, I, B, C4, UP, NPY, PD)
├── ty.toml                      # ty type-checker config
├── CLAUDE.md                    # Repo-level agent guidance
└── README.md                    # Public README
```

---

## Package Architecture

```mermaid
flowchart TD
    A["Source file<br/>(TOA5 / CSV)"] --> B["read_file()<br/>multigas.core.io"]
    A --> C["DataLoader.load()<br/>multigas.data.loader"]
    B --> C
    C --> D{Cache hit?}
    D -->|yes| E["joblib cache<br/>(.pkl)"]
    D -->|no| F["_load_csv()<br/>TOA5 detect --> pandas.read_csv"]
    F --> G["_normalize()<br/>NaN sentinels --> numeric coercion"]
    G --> E
    E --> H["MultiGasData<br/>(dataclass wrapping df + metadata)"]
    G --> H
    H --> I["Query API<br/>select_/where_/get / add_wind_*"]
    I --> J["pd.DataFrame result"]
```

Public entry points live at the top of the package:

- **`multigas.read_file`** — one-call convenience wrapper.
- **`multigas.DataLoader`** — full-control loader with cache management.

Both return a **`MultiGasData`** — a dataclass that wraps the loaded
DataFrame together with its `DatasetType`, absolute source path, and
`Query` mixin for fluent column selection, row filtering, and wind
analysis.

---

## Quick Start

```python
from multigas import read_file

ds = read_file("data/site_a.dat", dataset_type="1min")

ds.df.head()                       # underlying DataFrame (DatetimeIndex)
ds.dataset_type                    # <DatasetType.ONE_MINUTE: '1min'>
ds.source_path                     # absolute Path to the source file

# Fluent selection + filtering (Query mixin)
(
    ds.where("CO2", ">", 1.0)
      .where_date_between("2025-01-01", "2025-01-31")
      .select_columns(["CO2", "SO2"])
      .get()                       # commits the selection and returns the DataFrame
)

ds.refresh()                       # restore the pristine df_original
```

For full-control loading:

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

---

## Common Commands

```bash
uv sync                                     # install deps (including dev)
uv run main.py                              # run entry point
uv run ruff check --fix src/                # lint + auto-fix
uvx ty check src/                           # type check
uv run pytest tests/                        # run test suite
uv run pytest tests/test_imports.py -v      # circular-import check
```

---

## Glossary

| Term | Meaning |
|---|---|
| **TOA5** | Campbell Scientific LoggerNet ASCII table format — a first-line `"TOA5"` marker followed by header, units, sampling, and data rows |
| **DatasetType** | Enum whose string values are pandas frequency aliases (`"1s"`, `"2s"`, `"6h"`, `"1min"`) plus categorical modes (`"zero"`, `"span"`, `"wx"`) |
| **MultiGasData** | Dataclass wrapping a loaded DataFrame + provenance metadata; extends `Query` so all fluent helpers live directly on the result |
| **Query** | Mixin providing fluent column selection, row filtering, and null / empty inspection. Mutates its working `df` in place; `df_original` is the pristine copy restored by `refresh()` |
| **COMPARATOR** | List of accepted comparator aliases for `Query.where()` — symbolic (`">="`), English (`"greater than"`), and Indonesian (`"lebih besar sama dengan"`) |
| **normalise** | Replace `"NAN"` / `"NaN"` / `""` string sentinels with `np.nan` and coerce object-dtype columns to numeric where possible |
| **cache** | On-disk `joblib` pickle keyed by `md5(absolute_path + mtime)`; stored under `output/cache/*.pkl`. Stale or corrupted entries are dropped transparently |
| **ENABLE_LOG** | Environment variable (`"true"`/`"false"`) that gates loguru handler registration in `multigas.logging` |

---

## Related Files

- [`README.md`](../README.md) — Public-facing intro and installation
- [`CLAUDE.md`](../CLAUDE.md) — Agent guidance (rules, code style, commands)
- [`API Reference`](API-Reference.md) — Full public API with parameter tables
