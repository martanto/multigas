# Local MultiGas dashboard

The dashboard is a local, single-user React application backed by FastAPI.
Datasets are independent imports. Analysis filters never change record coverage.
Every plotted observation in the selected UTC range is displayed as scatter;
the initial range spans the whole dataset. Selecting a calendar day narrows it.

## Run

For first-time configuration, copy the repository-root `.env.example` to `.env`.
Keep an existing `.env` and add only the settings you need. The Python entry
points and Vite read the root configuration. Explicit arguments/CLI options
override process environment variables, which override `.env` values and defaults.
Vite also supports root `.env.local` and mode-specific overrides. Restart the
API and Vite after changing settings; no restart is performed during active imports.

| Variable | Default | Purpose |
|---|---|---|
| `ENABLE_LOG` | `false` | Enable console and file logging |
| `MULTIGAS_APP_DIR` | `output/app` | API and `main.py` persistent storage root |
| `MULTIGAS_UPLOAD_LIMIT_BYTES` | `5368709120` | Positive byte limit for HTTP uploads and local example staging |
| `MULTIGAS_DUCKDB_MEMORY_LIMIT` | `512MB` | DuckDB buffer memory; total plotting/browser memory is separate |
| `MULTIGAS_STATIC_DIR` | empty | Optional absolute `frontend/dist` path for API static hosting |
| `MULTIGAS_API_TARGET` | `http://127.0.0.1:8001` | Server-side Vite proxy destination |
| `MULTIGAS_EXAMPLE_SOURCE` | supplied Tangkuban Parahu Sec2 path | `main.py` source, overridden by `--source` |

Relative Python paths resolve from the process working directory. API listen
host/port remain Uvicorn command options; changing the proxy does not change
the API listener. These settings use no browser-visible `VITE_*` prefix.
`.env` and `.env.*` local files are ignored; `.env.example` is tracked. Never
put secrets in variables prefixed `VITE_`, which Vite exposes to browser code.

```powershell
uv sync --extra api
uv run --extra api uvicorn multigas.api.app:create_app --factory --host 127.0.0.1 --port 8001 --workers 1
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to port 8001.
Use one Uvicorn worker. `MULTIGAS_APP_DIR` changes the persistent storage root
(default `output/app`). To serve a production build from FastAPI, run
`npm run build` in `frontend`, set `MULTIGAS_STATIC_DIR` to the absolute
`frontend/dist` path, then open port 8001. The API reference is at `/docs`.

## Import and inspect

Choose **Import dataset**, upload CSV or Campbell Scientific TOA5 text, inspect
the preliminary sample, and confirm station, timestamp column, acquisition mode,
units, and normalization. Uploads stream to generated storage identifiers, with
a default 5 GiB limit. Executable serialization formats and binary files are
rejected. The API accepts staged identifiers rather than arbitrary server paths.

TOA5 units are read from the header. CSV units remain unconfirmed until supplied.
Naive timestamps mean UTC; timezone-aware values are converted to UTC. Every
timestamp and row is validated after confirmation, including rows beyond the
preview. Invalid timestamps fail the import; they are never silently dropped.

With normalization enabled, missing `RECORD` rows are removed, the last source
row wins duplicate timestamps globally, numeric types are checked over the full
file, and fixed-cadence sampling is checked after sorting. The first overall
record is kept; the first record following a gap is excluded. These decisions
apply across parser batches and midnight boundaries. Disable normalization to
retain all source observations. Counts and settings appear under provenance.

## Daily analysis

The coverage calendar includes missing dates. Coverage is the immutable record
count divided by the daily expectation, capped at 100%. Two-second data expects
**43,200 records per day**. `span` and `wx` completeness is undefined, displayed
as unavailable rather than zero. Channel validity counts finite readings after
filters; filtered sample count is a third, separate measurement.

Select a day, use previous/next available day, or edit both UTC range bounds.
Gas and ratio panels share time zoom and cursors. Charts load a complete Arrow
IPC stream in batches of at most 8,000 records, with numeric UTC timestamps.
The client retains every observation in typed scatter buffers. The separate
paged series endpoint is also full resolution. Batching is transport, not
downsampling. Large ranges take longer and
use browser memory proportional to the number of observations. Daily navigation
remains available while the full-range query loads.

Use **Analysis settings** to choose onboard or calculated ratios, add numeric
filters, select and arrange panels, and choose raw columns for tables/CSV.
Unknown units prevent calculations. Missing panels remain annotated. Statistics
and paginated rows use the same validated filters as exports. No shared mutable
`Query` objects are used by API requests.

**Save view** persists the dataset identifier, UTC range, channels, ratio source,
filters, and panel arrangement in SQLite. A missing dataset or selected column
is explained when restoring. The active analysis is also stored in URL parameters.
Theme preference is stored in the browser.

## Exports and persistence

CSV exports contain full-resolution filtered rows. Daily ZIPs contain one CSV
per selected day and a reproducibility manifest. Scientific exports use the
[ten-panel scatter renderer](Scientific-Plotting.md) and every source observation
in the requested range. Downloads also expose a separate manifest containing
source checksum, immutable dataset version, software version, UTC bounds,
filters, units, formulas, normalization settings, and rendering options.

Artifacts are cached by dataset version, software/rendering revision, and the
complete export specification. SQLite stores metadata, jobs, and views. Originals
and normalized, immutable daily Parquet files live beneath generated dataset
identifiers. No source path from an HTTP request is opened on the server.

One background worker processes imports and exports. Jobs expose progress,
cancellation, retry, and actionable failures. Cancellation is cooperative:
an active database operation or figure save finishes its current operation
before cancellation is observed; partial work is then removed. Publication is
atomic. Interrupted jobs are marked on restart and can be retried. Abandoned
staged uploads are removed after 24 hours on startup and before later uploads.

## Two-second Tangkuban Parahu example

```powershell
uv run --extra api main.py
```

The default source is
`D:\Data\Multigas Tangkuban Parahu\TANG_RTU\TANG_RTU_ChemData_Sec2.dat`.
The example declares `2s`, retains every record by default, imports into
`output/app`, and writes a full-range scatter summary plus manifest. Start
the dashboard against that storage root to browse it. `--normalize` opts in
to recorded exclusions; `--no-figure` imports only. `--source`, `--output`,
`--start`, `--end`, and `--format png|pdf|svg` override the defaults.
The original file is never modified. No six-hour file is merged into this example.

## Versioned API

| Endpoint under `/api/v1` | Purpose |
|---|---|
| `GET /health`, `GET /stations` | Health, shared panel definitions, station inventory |
| `POST /imports/preview?filename=...` | Raw text-body streaming upload and preliminary preview |
| `POST /imports/{id}/confirm` | Confirm `ImportSpec` and queue full validation |
| `GET /datasets`, `GET /datasets/{id}/days` | Provenance and immutable daily manifests |
| `GET /jobs`, `GET /jobs/{id}` | Persistent status and progress |
| `POST /jobs/{id}/cancel`, `POST /jobs/{id}/retry` | Cooperative cancellation and retry |
| `POST /series?offset=0&limit=8000` | Full-resolution Arrow IPC page; explicit UTC timestamps and counts |
| `POST /series/stream` | Complete Arrow IPC stream, bounded batches, numeric UTC epoch milliseconds |
| `POST /statistics`, `POST /rows?offset=0&limit=50` | Full-resolution statistics and bounded JSON rows |
| `GET /views`, `POST /views`, `DELETE /views/{id}` | Persistent analysis views and restoration checks |
| `POST /exports` | Queue CSV, daily ZIP, PNG, PDF, or SVG |
| `GET /downloads/{id}?manifest=true` | Artifact or accompanying manifest |

React components use CLI-generated shadcn/ui primitives under `frontend/src/lib/ui`.
TanStack Query owns server state; ECharts renders scatter points; Tailwind v4 is
configured through the Vite plugin. OpenAPI-generated TypeScript types live in
`frontend/src/lib/generated/api.d.ts`. Regenerate `tests/openapi.json` from
`create_app().openapi()`, then run `npm run types:api` in `frontend`.

## Verification

```powershell
uv run --extra api pytest tests/ --ignore=tests/test_logging.py -o cache_dir=tests/.pytest_cache --basetemp=tests/pytest-temp
uv run ruff check --fix src/
uvx ty check src/
cd frontend
npm run typecheck
npm run build
npm run test:e2e
```

Browser tests use installed Chrome and automatically launch isolated servers on
ports 8002/5174, storing data beneath `tests/e2e-storage`. They preserve imports
in the development app on ports 8001/5173. Screenshots, regression
fixtures, and benchmark reports are written beneath `tests/`.
The existing `tests/test_logging.py` targets the removed `multigas.config.logging`
API and currently prevents unqualified full-suite collection; it is unrelated to
this application and is not silently skipped in the pytest configuration.

The opt-in `uv run --extra api tests/benchmark_dashboard.py` generates a GB-scale
CSV and records import/export duration and peak memory. Full-resolution figure
and browser plotting memory grows with observation count; the DuckDB buffer
limit is not a cap on total Python/renderer memory.
