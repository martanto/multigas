# Logging

The `multigas` package ships a preconfigured [`loguru`](https://loguru.readthedocs.io/)
logger with three sinks: coloured console output, a general `DEBUG+`
rotating file, and an errors-only `ERROR+` rotating file. Handlers are
only registered when the `ENABLE_LOG` environment variable is
`"true"` (case-insensitive) — otherwise every `logger.*(...)` call is a
no-op.

> Back to [Home](Home.md) · Related: [Exceptions](Exceptions.md), [API Reference → Logging](API-Reference.md#logging-multigaslogging).

Module: `multigas.logging`.

---

## Quick Start

```python
from multigas.logging import logger, enable_logging

enable_logging()
logger.info("hello from multigas")
```

Or gate on an env var (recommended for CI / worker processes so children
inherit the value):

```bash
# One-shot run
ENABLE_LOG=true uv run python your_script.py

# Or add to .env at the repo root
echo 'ENABLE_LOG=true' >> .env
```

`multigas.logging` calls `load_dotenv(override=True)` at import time, so
the `.env` file is picked up automatically.

---

## Why It's Off by Default

Silence at import time is deliberate:

- Notebooks, ad-hoc scripts, and third-party callers don't want a
  package writing files to their working directory without asking.
- Test runs stay quiet unless a test explicitly opts in.
- Every `MultigasException` still calls `logger.log(...)` from its
  `__init__`, but with no handlers registered the call is a no-op — so
  the auto-log costs nothing when logging is off.

Turn it on when you want to *see* what the package is doing.

---

## Sinks

When `ENABLE_LOG=true` (or `enable_logging()` is called), three sinks
are registered against the shared `loguru` logger.

| Sink | Destination | Level | Retention | Rotation | Compression |
|---|---|---|---|---|---|
| Console | `sys.stderr` | `INFO` (default) | — | — | — |
| General log | `logs/multigas_YYYY-MM-DD.log` | `DEBUG+` | 30 days | Midnight | ZIP |
| Errors log | `logs/errors_YYYY-MM-DD.log` | `ERROR+` | 90 days | Midnight | ZIP |

Both file sinks use `enqueue=True` for thread- and process-safe writes.

### Formats

```
Console:   2026-09-22 14:03:11 | INFO     | multigas.data.loader:load:143 - Loaded from data/site_a.dat
File:      2026-09-22 14:03:11 | INFO     | multigas.data.loader:load:143 - Loaded from data/site_a.dat
```

Console output is coloured; file output is plain text.

---

## Runtime Toggles

All toggles live at `multigas.logging` and mutate the shared logger.

| Callable | Signature | Effect |
|---|---|---|
| `enable_logging` | `() -> None` | Register console + file sinks. Also sets `ENABLE_LOG=true` in `os.environ` so worker processes inherit the state. |
| `disable_logging` | `() -> None` | `logger.remove()` — drops all handlers. Also sets `ENABLE_LOG=false`. |
| `set_log_level` | `(level: str) -> None` | Re-register handlers with a new console-sink level. File sinks retain their fixed `DEBUG` / `ERROR` levels. |
| `set_log_directory` | `(log_dir: Path \| str) -> None` | Redirect file sinks to a new directory (created if missing) and log the change. |

```python
from multigas.logging import (
    logger,
    enable_logging,
    disable_logging,
    set_log_level,
    set_log_directory,
)

enable_logging()
set_log_level("DEBUG")                # verbose console
set_log_directory("./logs/session_A") # rotate to a new directory
logger.info("switched sinks")
disable_logging()                     # go quiet again
```

`set_log_level` accepts any loguru level name — `"DEBUG"`, `"INFO"`,
`"WARNING"`, `"ERROR"`, `"CRITICAL"` (case-insensitive).

---

## Verbose Mode on the Loader

Both `read_file` and `DataLoader` accept `verbose=True`. When set, the
loader emits `INFO` lines through the shared logger — but they still only
show up when `ENABLE_LOG=true` (or after `enable_logging()`).

```python
from multigas import read_file
from multigas.logging import enable_logging

enable_logging()
ds = read_file("data/site_a.dat", dataset_type="1min", verbose=True)
# 2026-09-22 14:03:11 | INFO | multigas.data.loader:load:182 - Cache dir: output/cache
# 2026-09-22 14:03:11 | INFO | multigas.data.loader:load:193 - Cache miss for data/site_a.dat. Loading from source.
# 2026-09-22 14:03:12 | INFO | multigas.data.loader:_load_csv:319 - Loaded from data/site_a.dat
# 2026-09-22 14:03:12 | INFO | multigas.data.loader:_normalize:358 - Normalizing data ...
# 2026-09-22 14:03:12 | INFO | multigas.data.loader:_normalize:373 - Dropped 3 duplicate row(s).
# 2026-09-22 14:03:12 | INFO | multigas.data.loader:_normalize:416 - Saved normalized file to output/normalized/site_a.csv
# 2026-09-22 14:03:12 | INFO | multigas.utils.validation:check_sampling_consistency:90 - Total rows: 44640
# ...
# 2026-09-22 14:03:12 | INFO | multigas.utils.cache:save_cache:131 - Cache saved to output/cache/....pkl.
```

`Query` operations (`select_numeric_columns`, `refresh`, `get`, …) share
the same pattern — they emit `INFO` lines only when the wrapping
`MultiGasData` (or the `Query` instance) has `verbose=True`. The
loader's `verbose` flag is **not** forwarded: a `MultiGasData` returned
by `read_file` / `DataLoader.load` starts with `verbose=False`, so set
`ds.verbose = True` yourself if you want `Query` log lines.

---

## Exceptions Auto-Log

Every `MultigasException` calls
`logger.opt(depth=1, exception=True).log(self._log_level, message)` from
its `__init__`. Three important consequences:

1. **Do not add a manual `logger.error(...)` before `raise`.** The
   exception already logs itself, so a manual call produces a duplicate.
   Fold any extra context into the exception message instead.
2. **`depth=1` shifts the recorded frame** so the log line's
   `{name}:{function}:{line}` slot points at the `raise` site, not at
   `MultigasException.__init__`.
3. **`exception=True` is guarded.** It only attaches a traceback when an
   exception is genuinely being handled (`sys.exc_info()[0] is not None`),
   so plain `raise SomeError("msg")` produces one clean line and
   `raise ... from e` produces a full chained traceback.

To change severity for a subclass, override the class-level `_log_level`
attribute (default `"ERROR"`):

```python
class MyWarning(MultigasException):
    _log_level = "WARNING"
```

See [`Exceptions`](Exceptions.md) for the full hierarchy.

---

## Environment Variable Contract

| Variable | Values | Effect |
|---|---|---|
| `ENABLE_LOG` | `"true"` (case-insensitive) | Handlers registered at package import time. |
| `ENABLE_LOG` | anything else (default `"false"`) | No handlers registered; all `logger.*` calls are no-ops. |

`multigas.logging` loads `.env` via `python-dotenv` with
`load_dotenv(override=True)` — a value in `.env` overrides one already
set in the shell. `enable_logging()` and `disable_logging()` also mutate
`os.environ["ENABLE_LOG"]` so child processes (multiprocessing workers,
joblib backends) inherit the parent's state.

---

## Directory Layout When Enabled

```
<cwd>/
└── logs/
    ├── multigas_2026-09-22.log      # DEBUG+, current day
    ├── multigas_2026-09-21.log.zip  # rotated at midnight, zipped
    ├── errors_2026-09-22.log        # ERROR+, current day
    └── errors_2026-09-21.log.zip
```

Rotation and compression happen automatically at midnight local time.

Change the directory with:

```python
from multigas.logging import set_log_directory
set_log_directory("/var/log/multigas")
```

---

## Common Patterns

### Log from your own code through the shared logger

```python
from multigas.logging import logger

logger.info("processing {} rows", len(ds.df))
logger.warning("column {!r} is entirely empty", "unused_ch")
```

Reusing the shared logger keeps your messages in the same files with
the same format as the package's own output.

### Silence noisy sub-calls temporarily

```python
from multigas.logging import disable_logging, enable_logging

disable_logging()
# ... code you don't want log output from ...
enable_logging()
```

Note this removes *all* handlers — package and any of your own added to
the shared logger — so re-add yours after `enable_logging()` if you had
custom ones.
