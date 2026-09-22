"""On-disk joblib cache helpers.

Provides the primitives used by :class:`multigas.data.loader.DataLoader` to
persist normalised DataFrames across runs:

- :func:`get_cache_key` derives a stable filename stem from the source file's
  absolute path and mtime.
- :func:`get_cache_path` resolves the ``.pkl`` path inside a cache directory.
- :func:`save_cache` serialises a DataFrame together with file metadata used
  to detect staleness on the next read.
- :func:`load_cache` reads a cached DataFrame back, validates it against the
  current source file, and treats a corrupted or stale entry as a soft
  failure (delete the file, return ``None``).
- :func:`clear_cache` deletes every ``.pkl`` file in a cache directory.

Cache entries become invalid automatically whenever the source file's mtime or
size changes.
"""

import hashlib
from pathlib import Path

import joblib
import pandas as pd

from multigas.logging import logger
from multigas.core.exceptions import CacheError


def get_cache_key(file_path: Path | str) -> str:
    """Generate a cache key from the absolute file path and its mtime.

    The key is an MD5 hex digest of ``"<absolute_path>_<mtime>"``, so it
    changes automatically whenever the source file is modified.

    Args:
        file_path: Path to the source file.

    Returns:
        Hex-encoded MD5 digest string used as the cache filename stem.

    Example:
        >>> key = get_cache_key(Path("data/site_a.csv"))
        >>> len(key)
        32
    """
    resolved_path = Path(file_path)
    mtime = resolved_path.stat().st_mtime
    key_string = f"{resolved_path.absolute()}_{mtime}"
    return hashlib.md5(key_string.encode()).hexdigest()


def get_cache_path(cache_dir: Path | str, file_path: Path | str) -> Path:
    """Resolve the on-disk path for a cached version of a source file.

    Args:
        cache_dir: Directory where cache files are stored.
        file_path: Path to the source file whose cache path is resolved.

    Returns:
        Absolute path to the ``.pkl`` cache file inside ``cache_dir``.

    Example:
        >>> path = get_cache_path("/tmp/cache", "data/site_a.csv")
        >>> path.suffix
        '.pkl'
    """
    cache_dir: Path = Path(cache_dir)
    cache_key = get_cache_key(file_path)
    return cache_dir / f"{cache_key}.pkl"


def save_cache(
    df: pd.DataFrame,
    file_path: Path | str,
    cache_dir: Path | str,
    verbose: bool = False,
) -> None:
    """Serialise a DataFrame to the on-disk cache.

    Stores the DataFrame alongside file metadata (absolute path, mtime,
    mtime_ns, size) so that :func:`get_cache_path` can validate staleness on
    the next read. When the target cache file already exists the write is
    skipped — the cache key incorporates the source file's mtime, so an
    existing entry with the same key already represents the same source
    state and re-serialising it would just be redundant I/O.

    Args:
        df: Normalised DataFrame to cache.
        file_path: Path to the original source file. Used to derive the cache
            key and to record file metadata.
        cache_dir: Directory where the ``.pkl`` cache file is written.
        verbose: Log the cache file path after a successful write, or the
            skip message when an entry already exists. Defaults to ``False``.

    Raises:
        CacheError: If the joblib dump fails for any reason.

    Example:
        >>> import pandas as pd
        >>> from pathlib import Path
        >>> df = pd.DataFrame({"CO2": [1.2, 3.4]})
        >>> save_cache(df, Path("data/site_a.dat"), Path("/tmp/cache"))
    """
    file_path: Path = Path(file_path)
    cache_path = get_cache_path(cache_dir, file_path)

    if cache_path.exists():
        if verbose:
            logger.info(f"Cache already exists, skipping write: {cache_path}")
        return

    try:
        # Snapshot the source file's stat once so mtime / mtime_ns / size
        # cannot drift mid-write (e.g. if the datalogger appends new rows
        # between the three separate stat() calls the old version used).
        source_stat = file_path.stat()
        cached_data = {
            "dataframe": df,
            "metadata": {
                "file_path": str(file_path.absolute()),
                "mtime": source_stat.st_mtime,
                "mtime_ns": source_stat.st_mtime_ns,
                "size": source_stat.st_size,
            },
        }

        joblib.dump(cached_data, cache_path, compress=3)

        if verbose:
            logger.info(f"Cache saved to {cache_path}.")

    except Exception as e:
        raise CacheError(f"Cache write failed: {e}") from e


def load_cache(
    file_path: Path | str,
    cache_dir: Path | str,
    verbose: bool = False,
) -> pd.DataFrame | None:
    """Load a cached DataFrame if the on-disk entry is still valid.

    Resolves the cache path via :func:`get_cache_path`, then validates the
    stored metadata (``mtime_ns`` + ``size``, or the legacy ``mtime`` fallback)
    against the current source file's ``stat()``. Stale or corrupted cache
    files are deleted automatically. A corrupted cache is a soft failure —
    the entry is removed, a warning is logged, and ``None`` is returned so
    the caller can transparently reload from source.

    Args:
        file_path: Path to the original source file whose cache entry to load.
        cache_dir: Directory where the ``.pkl`` cache files live.
        verbose: Log the cache path on hit and log a warning when the cache
            is stale. A corrupted-cache warning is always logged regardless
            of this flag. Defaults to ``False``.

    Returns:
        The cached DataFrame when a valid entry exists, ``None`` on a cache
        miss, a stale entry, or a corrupted cache file.

    Example:
        >>> from pathlib import Path
        >>> df = load_cache(Path("data/site_a.dat"), Path("/tmp/cache"))
        >>> df is None  # cache miss on first run
        True
    """
    file_path = Path(file_path)
    cache_path = get_cache_path(cache_dir, file_path)

    if not cache_path.exists():
        return None

    try:
        if verbose:
            logger.info(f"Loading from cache: {cache_path}")

        cached_data = joblib.load(cache_path)

        if isinstance(cached_data, dict):
            df = cached_data.get("dataframe")
            metadata = cached_data.get("metadata", {})

            stat = file_path.stat()
            mtime_ns = metadata.get("mtime_ns")
            size = metadata.get("size")

            if verbose:
                logger.info("Cache loaded successfully.")

            if mtime_ns is not None and size is not None:
                if mtime_ns == stat.st_mtime_ns and size == stat.st_size:
                    return df
            elif metadata.get("mtime") == stat.st_mtime:
                return df

        cache_path.unlink(missing_ok=True)

        if verbose:
            logger.warning(f"Cache invalid: {cache_path}")

        return None

    except Exception as e:
        cache_path.unlink(missing_ok=True)
        logger.warning(f"Cache invalid, will reload: {cache_path} ({e})")
        return None


def clear_cache(cache_dir: Path | str, verbose: bool = False) -> None:
    """Delete all ``.pkl`` cache files from a cache directory.

    Iterates over every ``*.pkl`` file in ``cache_dir`` and removes it. The
    ``file_path`` parameter is accepted for API symmetry but is not used — all
    cache files in the directory are deleted regardless of source.

    Args:
        cache_dir: Directory whose ``.pkl`` files will be deleted.
        verbose: Log the total number of deleted files. Defaults to ``False``.

    Example:
        >>> clear_cache(Path("data/site_a.dat"), Path("/tmp/cache"), verbose=True)
        # INFO: Deleted 3 cache files.
    """
    cache_dir: Path = Path(cache_dir)

    count = 0
    for cache_file in cache_dir.glob("*.pkl"):
        try:
            cache_file.unlink()
            count += 1
        except Exception as e:
            logger.warning(f"Failed to delete cache file {cache_file}: {e}")

    if verbose:
        logger.info(f"Deleted {count} cache files.")
