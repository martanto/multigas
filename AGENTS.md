# AGENTS.md

This file provides guidance to Claude Code and Codex when working with code in this repository.

## Project Overview

`multigas` is an early-stage Python package for processing and analyzing multi-gas volcanic monitoring data (CO2, SO2, H2S) from Campbell Scientific dataloggers. Developed in collaboration with CVGHM and USGS.

The data is inherently **time-series**: every dataset is a stream of gas / calibration / weather readings sampled over time, and every DataFrame flowing through the package is expected to carry a `pd.DatetimeIndex`. Sampling-interval `DatasetType` members (`"1s"`, `"2s"`, `"6h"`, `"1min"`) are pandas frequency aliases for exactly this reason.

## Package Manager

This project uses [UV](https://docs.astral.sh/uv/) as its package manager. Always use `uv` (and `uvx` for tool invocations) — never `pip`, `pip install`, or `python -m pip`.

## Commands

```bash
# Install dependencies (including dev)
uv sync

# Run the entry point
uv run main.py

# Lint and auto-fix
uv run ruff check --fix src/

# Type check
uvx ty check src/

# Run all tests (output stays in tests/)
uv run pytest tests/

# Run a single test file
uv run pytest tests/path/to/test_file.py

# Run a single test
uv run pytest tests/path/to/test_file.py::test_function_name

# Check for circular imports after any module change
uv run pytest tests/test_imports.py -v
```

## Architecture

The package lives in `src/multigas/` (src layout).

```
src/multigas/
├── __init__.py          # Exposes version metadata, read_file, DataLoader
├── logging.py           # Package-level logger (loguru)
├── config/              # Configuration (stub)
├── cli/
│   ├── __init__.py       # CLI package marker
│   ├── main.py           # Click root command and console-script entry point
│   └── commands/
│       ├── normalize.py  # Normalize a source file and write a CSV summary
│       ├── extract.py    # Select dates and extract daily CSVs/completeness
│       └── plot.py       # Six-hour and selected-column plotting commands
├── core/
│   ├── __init__.py      # Re-exports DatasetType, enums, type aliases, exceptions
│   ├── types.py         # DatasetType, SensorStatus, FileFormat, LogLevel, DatasetMetadataDict
│   ├── query.py         # Query — fluent column/filter mixin extended by MultiGasData
│   ├── constant.py      # COMPARATOR, WIND_DIRECTIONS_{4,8,16}, WIND_QUADRANTS_{4,8}
│   ├── io.py            # read_file — one-call convenience wrapper around DataLoader
│   └── exceptions.py    # Exception hierarchy (MultigasException and subclasses)
├── data/
│   ├── __init__.py      # Re-exports DataLoader, MultiGasData
│   ├── loader.py        # DataLoader — file I/O, normalisation, joblib caching
│   └── multigas_data.py # MultiGasData — DataFrame + provenance wrapper (extends Query)
├── plot/
│   ├── __init__.py      # Lazily exposes Plot, plot_columns and plot_completeness
│   ├── columns.py       # Selected numeric columns: observation-only PNG / PDF / HTML
│   ├── dimensions.py    # Backend-free size validation and shared layout budgets
│   ├── plot.py          # Plot — public six-hour plotting API (PNG / PDF / HTML)
│   ├── six_hours.py     # Ten-panel layout: trend, y_axis, gaps, caption, log_ticks + matplotlib / Bokeh renderers
│   └── plot_completeness.py # plot_completeness — daily-completeness PNG via data-availability
└── utils/
    ├── path.py          # ensure_dir helper
    ├── cache.py         # get_cache_key / get_cache_path / save_cache / load_cache / clear_cache
    ├── validation.py    # check_columns_exist (+ validate_dataframe_column wrapper) and check_sampling_consistency
    └── dataframe.py     # to_datetime_index, get_dates, convert_to_wind_direction, convert_to_wind_quadrant, calculate_completeness, count_csv_rows
```

Public entry points: `read_file` (one-call convenience) and `DataLoader` (full-control loader). Both return a `MultiGasData` (from `multigas.data.multigas_data`, re-exported as `multigas.data.MultiGasData`) — a class wrapping the loaded DataFrame, its `DatasetType`, and source path, with `Query` methods for fluent column selection and filtering. Cached results are persisted via `joblib`.

The installed `multigas` console script resolves to `multigas.cli.main:cli`.
The root Click group registers `normalize`, `extract`, and `plot`. `normalize`
writes a normalized CSV; `extract` optionally applies inclusive date bounds and
delegates daily output to `MultiGasData.extract_daily`; `plot` preserves the
legacy `plot CSV_PATH` form for six-hour plots and also exposes
`plot columns COLUMN_NAMES...` for selected numeric columns. CLI commands use
Rich summaries by default and support JSON output where documented.

`Query` mutates `self.df` in place: `where(column, comparator, value)` filters rows using any alias from `COMPARATOR` (symbolic, English, or Indonesian — the index is used when `column` equals `index_col`); `select_columns(...)` / `select_numeric_columns(...)` stage a column selection; `get()` commits it by narrowing `self.df` and recomputing `numeric_columns`. Use `refresh()` to restore the pristine `df_original` — it is the only way to bring dropped rows or columns back.

`DatasetType` string values are pandas frequency aliases (`"1s"`, `"2s"`, `"6h"`, `"1min"`) for the four sampling-interval members, plus the categorical values `"zero"`, `"span"`, `"wx"` for calibration/weather modes. Two properties are exposed on every member: `.total_data` (expected records per day; defined for sampling-interval members and `ZERO`, raises `ValueError` for `SPAN` / `WX`) and `.label` (hyphenated form such as `"one-minute"`, safe on every member — used as a path segment by `extract_daily`). `.label` is deliberately not called `.name` so it doesn't shadow the built-in `enum.Enum.name` attribute that `_missing_` relies on when reporting invalid values.

`Plot` accepts `columns=1` for ten vertically stacked panels or `columns=2`
(default) for five rows. The CLI exposes this as `--one-column`. Both output
periods and all formats (PNG, PDF, HTML) use the selected layout. Static
figures measure 280 x 190 mm by default and 280 x 380 mm in one-column mode.

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

`multigas.plot.plot_columns` is a lazy public API in `plot/columns.py` for
selected numeric columns and every dataset type. CLI `plot columns` requires
names, `--source`, and `--dataset-type`; the Click group dispatcher preserves
`plot CSV_PATH`. Path sources use normalized loading without cache, retaining
empty columns; loaded `MultiGasData` is used directly without mutation.
Validate names together with `check_columns_exist`, reject nonnumeric columns
together, and apply inclusive date bounds before rendering. The adaptive
one/two-column layout plots finite observations only on shared datetime and
linear full-range axes, with no smoothing, clipping or outage shading.
Every PNG/PDF/HTML figure includes a below-panel caption with source, dates,
exclusions and relevant gas caveats. Output replaces
`figures/<source-stem>-columns.<extension>`; JSON reports `{"figure": "..."}`.

`MultiGasData.extract_daily` writes `<slug>-completeness.csv` and, unless `plot=False`, renders it to a PNG via `multigas.plot.plot_completeness`. The plot import is deliberately lazy (inside `extract_daily`) so `import multigas` never loads matplotlib — keep it that way (guarded by `tests/test_plot.py`). Plotting is a soft failure: `plot_completeness` logs a `WARNING` and returns `None` rather than aborting the extraction, and always closes its figure.

The loader currently reads Campbell Scientific TOA5 or plain CSV files; there
is no active Excel-reading branch despite `openpyxl` being declared as a
runtime dependency. Core runtime dependencies include `pandas`, `numpy`,
`openpyxl`, `loguru`, `joblib`, `python-dotenv`, and `python-slugify`. The CLI
adds `click` and `rich`; plotting adds `matplotlib`, `seaborn` (scoped
styling only), `bokeh`, and `data-availability`.

`DataLoader.load` with `normalize=True` runs `_normalize` (NaN sentinels → drop missing `RECORD` → dedupe timestamps keeping the last → numeric coercion) and then, for sampling-interval `DatasetType`s only, keeps just the rows that `check_sampling_consistency` marks as regularly spaced — the first row after every gap is dropped too. The filtered frame is what gets cached.

## Documentation (Wiki)

The `wiki/` directory is the single source of truth for project
documentation. Prefer reading these pages over re-deriving information
from source — they are kept in sync with the code and use it as a
knowledge base for any task.

| File | Description |
|---|---|
| [`wiki/Plot.md`](wiki/Plot.md) | Standard six-hour and selected-column plotting APIs, CLI examples, date slicing, captions, styles, and PNG/PDF/HTML exports. |
| [`wiki/Home.md`](wiki/Home.md) | Landing page. Holds the navigation table (add every new wiki page here), the repository map, the package-architecture Mermaid diagram, a quick-start snippet, common `uv` / `uvx` commands, and a glossary of project vocabulary (TOA5, `DatasetType`, `MultiGasData`, `Query`, `COMPARATOR`, normalisation, cache layout, `ENABLE_LOG`). Start here when orienting to the project. |
| [`wiki/Getting-Started.md`](wiki/Getting-Started.md) | First-run guide. Prerequisites, `uv sync` install walkthrough, first-load example via `read_file`, a Mermaid diagram of the load pipeline (cache lookup → `_load_csv` → `_normalize` → `save_cache`), full-control loading with `DataLoader`, fluent-query patterns (`select_columns`, `where` / `where_date` / `where_date_between` / `where_values_between`, chaining + `get()`, `refresh()`, `missing_columns` / `empty_columns`), wind analysis (`add_wind_direction` / `add_wind_quadrant`), enabling logging, error-handling starter snippet, and the `uv` / `uvx` dev workflow. Read this before answering "how do I use this package". |
| [`wiki/CLI-Reference.md`](wiki/CLI-Reference.md) | Click command reference for `normalize`, `extract`, `plot`, and `plot columns`, including source locations, defaults, date bounds, output paths, and JSON fields. |
| [`wiki/API-Reference.md`](wiki/API-Reference.md) | Full public-API surface. Every callable listed with its signature and a parameter table (name / type / default / description). Covers `read_file`, `DataLoader.__init__` / `.load` (with a cache-flow Mermaid diagram), the `MultiGasData` class + `add_wind_direction` / `add_wind_quadrant`, the full `Query` mixin (properties + 13 methods + static helpers), all four enums (`DatasetType`, `SensorStatus`, `FileFormat`, `LogLevel`), type aliases + `DatasetMetadataDict`, the exception hierarchy, `multigas.logging` toggles + file-sink retention, every helper in `multigas.utils.*`, `multigas.plot.plot_completeness` (soft-failure PNG renderer used by `extract_daily`), and the constants in `multigas.core.constant` including the per-operator alias table for `COMPARATOR` (symbolic / English / Indonesian). Read this for exact signatures, parameter defaults, and raised exceptions. |
| [`wiki/Queries.md`](wiki/Queries.md) | Complete `Query` method index with constructor, properties, argument types, defaults, mutation semantics, and examples. |
| [`wiki/Data-Columns.md`](wiki/Data-Columns.md) | Per-column dictionary for the Campbell Scientific multi-GAS TOA5 / CSV output. Every datalogger column grouped by role — system metadata (`TIMESTAMP`, `RECORD`, `Site_Name`, `Duty_Cycle`, `Status_Flag`), power / instrument temperature (`Avg_batt_volt`, `Avg_regulated_volt`, `Avg_PTemp`), meteorological sensors (`Avg_AirT` / `Avg_AirRH` / `Avg_FumaroleT` / `Avg_SampleP` / `Avg_AirP` / `Avg_Wind_Speed` / `Avg_Wind_Direction`), gas concentrations (`H2O`, `Avg_CO2_lowpass`, `Avg_SO2`, `Avg_H2S`), and the four ratio families (H2O/CO2, CO2/SO2, H2S/SO2, CO2/S_tot) each with `Avg_*_ratio` / `Avg_*_intercept` / `#_valid_*_ratios` — plus the sulfur-proportion pair. Documents the shared onboard-regression contract (3-minute sliding window, `r² > 0.7`, positive slope, minimum-gas threshold, up to 1800 valid ratios per 30-minute cycle at 1 Hz), units where applicable (°C / hPa / % / degrees), and the uncorrected-H2S cross-sensitivity caveat that propagates into every H2S-based ratio and both sulfur proportions. **Read this whenever the user asks what a column means, what its unit is, or why an H2S-derived value looks off.** |
| [`wiki/Logging.md`](wiki/Logging.md) | Logging deep dive. Rationale for silent-by-default behaviour; per-sink table (console + `multigas_*.log` DEBUG+/30d + `errors_*.log` ERROR+/90d with rotation/compression); console vs file format samples; runtime toggle reference (`enable_logging`, `disable_logging`, `set_log_level`, `set_log_directory`); interaction with `verbose=True` on `read_file` / `DataLoader`; the `MultigasException` auto-log contract (`depth=1`, guarded `exception=True`); `ENABLE_LOG` env-var contract with `python-dotenv` and worker-process inheritance; on-disk log directory layout; common patterns (reusing the shared logger, temporarily silencing sub-calls). Read this before touching anything logger-related. |
| [`wiki/Exceptions.md`](wiki/Exceptions.md) | Exception hierarchy reference. ASCII + Mermaid tree; per-class table listing parent, raise condition, and typical source (`MultigasException`, `DatasetError`, `FilterError`, `ColumnError`, `DateRangeError`, `ValidationError`, `CacheError`, `LoaderError`, `MetadataError`, `PlotError`, `ConfigError`); annotated `MultigasException.__init__` showing the auto-log mechanics; `_log_level` override recipe; soft-vs-hard-failure pattern with the `load_cache` example; catching patterns (broad `MultigasException`, `DatasetError`-scoped, per-class narrow, `raise ... from e`); what-not-to-do checklist (no manual `logger.error` before `raise`, no swallowed exceptions, no hand-rolled column checks); template for adding a new subclass. Read this whenever raising, catching, or defining an exception. |
| [`wiki/Wind-Analysis.md`](wiki/Wind-Analysis.md) | Wind-direction and quadrant reference. Full tables for `WIND_DIRECTIONS_4` / `_8` / `_16` and `WIND_QUADRANTS_4` / `_8` with center degree, inclusive-lower / exclusive-upper ranges, and the wrap-around-North explanation (why every sector table stores North twice). Contract for `MultiGasData.add_wind_direction` / `add_wind_quadrant` and the underlying `convert_to_wind_direction` / `convert_to_wind_quadrant` scalar helpers, including NaN handling, `% 360` normalisation, and `ValidationError` on a bin miss. Names [QWeather Legacy Wind Direction](https://dev.qweather.com/en/docs/api/weather/wind-guide/#legacy-wind-direction) as the canonical source for the 16-sector table and calls out that 8- and 4-sector tables follow standard meteorological convention. Read this whenever editing a `WIND_*` constant or writing new wind-analysis code. |

Pages still to add once their subject packages are complete:
`Data-Loading.md`, `Caching.md`, `Contributing.md`.
When you add one, also append a row to the table above (and to the
navigation table in `wiki/Home.md` and the documentation table in
`README.md`) so this stays the single index.

## Rules

1. **Log every completed task in the daily changelog.** Any finished task — bug fix, refactor, new feature, test, documentation change — must have its outcome recorded in `changelogs/YYYY-mm-dd.md` (using today's date) before moving on. Create the file if it does not exist. Append new entries; never overwrite previous entries in the same file. The `changelogs/` directory is git-ignored (local only).
2. **Type checker is `ty`.** Use `uvx ty check src/` for type checking.
3. **Lint with ruff.** Use `uv run ruff check --fix src/` for linting.
4. **All `uv`, `uvx`, and `python` commands are permitted.** `uv sync`, `uv run`, `uv pip install/uninstall`, `uv lock`, `uvx ty check`, `python main.py`, etc. — no need to ask.
5. **ALWAYS create a new branch before any commits or modifications.** Use `git checkout -b <prefix>/<branch-name>`. Choose prefix by work type: `fix/` for bug fixes, `ft/` for new features, `dev/` for everything else. Never work directly on `main` or `master`.
6. **Always use the `tests/` directory for test output.** Create all test output inside `tests/`, placed at the same level as the test file that produces it (e.g. output from `tests/test_foo.py` goes into `tests/`, not a subdirectory or the project root).
7. **User will do all commits after review.** Do not commit — stage or prepare changes only.
8. **Run circular import test after every module change.** After adding, removing, or reorganising any module or import, run `uv run pytest tests/test_imports.py -v` to confirm no circular imports were introduced.
9. **DataFrames must carry a `pd.DatetimeIndex`.** Every dataset in this package is time-series, so any DataFrame that is stored on `MultiGasData`, passed between `Query` methods, cached, or returned to a user is expected to be indexed by time. `Query.__init__` uses `to_datetime_index` from `multigas.utils.dataframe` when it receives a source timestamp column; the loader's `_load_csv` currently performs the initial timestamp promotion before constructing `MultiGasData`. Preserve a `DatetimeIndex` at every ingest/conversion boundary, use `to_datetime_index` for new conversion paths, and route any future loader refactor through that helper rather than duplicating conversion logic.
10. **Prefer available time-series analysis skills over ad-hoc code.** Because every dataset here is time-series, whenever a task calls for time-series operations — forecasting, resampling strategy, gap / sampling-rate diagnostics, decomposition, anomaly detection, autocorrelation, statistical testing on temporal data, plotting time-series correctly — first check the skills roster surfaced for the session and invoke a fitting one via the `Skill` tool instead of writing the analysis from scratch. Skills to reach for when they apply (only if listed for this session): `timesfm-forecasting` (zero-shot univariate forecasting on any of our gas / weather series), `statistical-analysis` and `statsmodels` (test selection, ARIMA / GLM / mixed models, diagnostics on temporal data), `seaborn` / `matplotlib` / `plotly` / `scientific-visualization` (time-series plots done right — no `.values`, colorblind-safe palettes, proper axis handling), `polars` / `dask` / `vaex` (when a dataset is too large for pandas). Skip the skill only when it is genuinely not available, the task is trivially small, or the user explicitly asks for a hand-rolled solution — and say so in your response when you do.
11. **Documentation updates are comprehensive.** When asked to add or update docs, update ALL of: `wiki/*.md` and `README.md`. Also update `CLAUDE.md` for architecture/design changes. A doc change is not done until every affected surface is in sync — the wiki page(s) that cover the topic, the public `README.md`, and (when the change touches architecture, public API shape, rules, or code-style conventions) the *Architecture*, *Documentation (Wiki)*, *Rules*, or *Code Style* sections of this file. Adding a new wiki page also means adding a row to both the navigation table in `wiki/Home.md` and the *Documentation (Wiki)* table in `CLAUDE.md`. Do not leave one surface stale when another has been updated.
12. **GitHub wiki syncs from the local `wiki/` directory.** Whenever the user asks to update the GitHub wiki (`https://github.com/martanto/multigas.wiki.git`), treat every markdown file inside `wiki/` as the source of truth. Clone the wiki repo (default to the session scratchpad), copy every `wiki/*.md` file over — do not cherry-pick a subset — then commit and push. The user has pre-authorised fetch, pull, commit, and push against the wiki repo, so no extra confirmation is needed for those operations.

## Plot and Figure Styling

**Use this section as the default reference whenever the user asks to create
or modify a plot or figure in this repository.** Follow explicit user styling
requests when they differ. Start from `src/multigas/plot/plot.py` (the public
API) and `src/multigas/plot/six_hours.py` (the actual styling constants and
renderers); see `wiki/Plot.md` for the plotting guide. Re-read the relevant
source before implementation so this reference stays aligned with the code.
Reuse the visual style for other figure types, adapting dimensions and type
sizes to the intended medium. The ten-panel arrangement, rolling median,
ratio scaling, and outage threshold are six-hour time-series conventions;
apply them to other data only when appropriate.

- **Appearance:** compact, Nature-inspired scientific panels on a white
  background, with restrained decoration, black titles, chemical subscripts,
  and consistent series colors across panels, date windows, and formats.
- **Layout:** six-hour plots have ten panels in row-major order, five rows
  by two columns by default (`columns=2`), or ten rows with `columns=1`
  (`--one-column`). Static size is 280 x 190 mm or 280 x 380 mm respectively,
  including the caption. Use shared time axes and date labels only on the
  bottom row. Constrained layout uses `hspace=0.18`, `wspace=0.06`, outer
  padding, and a reserved caption band below the panels.
- **Typography:** sans-serif, preferring Arial, then Helvetica, then DejaVu
  Sans; matching sans-serif mathtext. Static sizes in points: figure heading
  8.5 bold; panel titles 7.6 bold, left-aligned with `(a)` through `(j)`;
  axis labels 6.6; tick labels and legend 6.3; caption 6.2; right-aligned
  sample counts and clipping notes 5.8. Text is `#171717`, muted text
  `#5A5A5A`. These sizes describe the current full-size export, not a
  universal requirement for slides or smaller figures.
- **Axes and grid:** hide top/right spines; remaining axes and major tick
  widths are 0.55 pt. Major ticks are 2 pt long with 2 pt padding; minor
  ticks are 1.2 pt long and 0.4 pt wide. Major gridlines on both axes are
  `#D2D2D2`, 0.3 pt, dashed `(4, 3)`, behind the data. Use concise date
  formatting with 4-8 major ticks. Where negative observations cross zero
  on a linear axis, add a `#9A9A9A`, 0.4 pt zero line.
- **Observations and trends:** circular scatter points without outlines,
  area 6 pt² and alpha 0.65; for more than 1,000 rows, area 3.5 pt² and
  alpha 0.4. The six-hour trend is a centred 7-day rolling median of daily
  medians, requiring at least three valid days, with breaks across gaps.
  Draw it 0.9 pt wide in the series color multiplied by 0.6 per RGB channel,
  with a 2 pt white halo. Keep timestamps on the x-axis; never replace
  elapsed time with row positions or silently interpolate missing readings.
- **Scale and missing data:** six-hour ratio axes are linear by default.
  `Plot(..., log_scale=True)` / CLI `--log-scale` enables log scale for
  panels (a)-(e) when all values are positive, regardless of range. Panels
  with zero or negative ratios and panels (f)-(j) remain linear. Both
  periods and all formats use the option and captions describe it. Robust limits
  omit an extreme only beyond twice the 1st-99th percentile span; static
  plots mark off-axis values with open triangles (area 9 pt², 0.5 pt edge)
  and count them beside `n`. Do not silently discard outliers. Outages
  longer than two days get black shading at alpha 0.025. Empty panels say
  "No valid readings in this period" in muted text.
- **Proportions:** SO2 uses orange circles and H2S uses deep-blue squares
  for stronger contrast. Panel (j) displays ticks at 0, 25, 50, 75, 100 %
  with limits -5 to 105 %. Static legends are frameless, two columns,
  above the panel beside its title.
- **Caption:** place a wrapped explanatory paragraph directly below the
  panels. State source/date range, units, transformations, trends, gaps,
  and off-scale conventions. For six-hour gas data preserve the missing
  TOA5-unit caveat, uncorrected H2S cross-sensitivity caveat, and SO2
  baseline warning when the median is at or below zero. Never invent units.
- **Export and implementation:** PNG at 300 dpi with a white background;
  editable vector PDF with PDF/PS font type 42. HTML uses Bokeh with the
  same series mapping and scientific conventions, linked time axes and
  hover values. Keep Matplotlib/Seaborn styling scoped with `rc_context`
  and `axes_style("ticks")`; preserve lazy plotting imports and always
  close static figures. Inspect new rendered figures at their intended
  size for clipping, readable labels, and overlapping captions/legends.

The fixed extended Nature Reviews palette used by the current renderer is:

| Panel | Series | Color |
|---|---|---|
| (a) | CO2/S total | `#738135` |
| (b) | H2S/SO2 | `#24743A` |
| (c) | CO2/H2S | `#136878` |
| (d) | CO2/SO2 | `#0E4F90` |
| (e) | H2O/CO2 | `#7A2C75` |
| (f) | CO2 | `#9D2823` |
| (g) | SO2 | `#B75226` |
| (h) | H2S | `#9C792C` |
| (i) | H2O | `#75503E` |
| (j) | SO2 / H2S proportions | `#B75226` / `#0E4F90` |

Use labels and marker shapes as well as color to distinguish series.
This is the project's current style, not a certification of journal compliance.

## Code Style

- **Linter**: Ruff with rules E, W, F, I, B, C4, UP, NPY, PD (see `ruff.toml`)
- **Docstrings**: Google convention — each docstring must include: a short one-line description, an optional extended description, `Args:` with type annotations, `Raises:` for any exceptions, `Returns:` with type, and a brief `Example:` block
- **Line length**: 88
- **Type checker**: `ty` (see `ty.toml`)
- - Tests and `scripts/` directories are excluded from Ruff; `__init__.py` allows unused imports (F401)
- Always use `.to_numpy()` instead of `.values` when extracting numpy arrays from pandas objects.
- Always use `.isna()` instead of `.isnull()` for null checks.
- **Imports**: isort-sorted; `multigas` is known first-party
- **Never call `logger.error(...)` / `logger.warning(...)` immediately before `raise <MultigasException>(...)`.** `MultigasException.__init__` already auto-logs the message (at `_log_level`, `"ERROR"` by default) with the caller's frame and the active traceback. Fold any extra context into the exception's message so the log line and the traceback stay in sync. To lower the severity of a subclass, override its `_log_level` (e.g. `_log_level = "WARNING"`), don't add a manual log call.
- **Don't raise a `MultigasException` you know the caller will catch-and-suppress.** If a failure is a recoverable soft outcome (e.g. a stale or corrupted cache), return a sentinel — `None`, an empty collection — from the source function and log at `WARNING` there. Reserve `raise` for conditions the caller treats as real errors. See `multigas.utils.cache.load_cache` for the pattern.
- **Use `check_columns_exist` (from `multigas.utils.validation`) for column-existence checks.** Accepts `str | list[str]`, raises `ColumnError` (auto-logged) once with every missing name in the message. Don't hand-roll `if column not in columns: raise ...` — the utility already batches the report, and `validate_dataframe_column` is the DataFrame-aware wrapper on top of it.
