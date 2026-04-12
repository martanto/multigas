"""Data loading with caching and normalization."""

import hashlib
from pathlib import Path

import numpy as np
import joblib
import pandas as pd

from multigas.logging import logger
from multigas.core.types import DatasetType, LoadedDataset
from multigas.utils.path import ensure_dir
from multigas.core.exceptions import CacheError, LoaderError


class DataLoader:
    """Handles file I/O, normalization, and caching.

    Attributes:
        cache_dir: Directory for cached normalized files.
        verbose: Whether to emit informational log messages.

    Example:
        >>> loader = DataLoader(cache_dir="output/cache", verbose=True)
        >>> dataset = loader.load("data/site_a.csv", dataset_type="co2")
    """

    def __init__(self, cache_dir: Path | str | None = None, verbose: bool = False):
        """Initialize data loader.

        Args:
            cache_dir: Cache directory. Defaults to ``./output/cache``.
            verbose: Whether to emit informational log messages.

        Example:
            >>> loader = DataLoader()
            >>> loader_custom = DataLoader(cache_dir="/tmp/cache", verbose=True)
        """
        if cache_dir is None:
            cache_dir = Path("output/cache")

        self.cache_dir: Path = Path(cache_dir)
        self.verbose = verbose

    def load(
        self,
        file_path: Path,
        dataset_type: DatasetType | str,
        normalize: bool = True,
        use_cache: bool = True,
    ) -> LoadedDataset:
        """Load data from file with optional normalization and caching.

        Attempts to serve from cache when both ``use_cache`` and ``normalize``
        are ``True``. On a cache miss the file is read from disk, optionally
        normalized, and the result is written back to the cache.

        Args:
            file_path: Path to the source CSV file.
            dataset_type: Dataset type identifier (``DatasetType`` or its string
                value).
            normalize: Whether to replace NAN strings with ``np.nan`` and
                coerce object columns to numeric. Defaults to ``True``.
            use_cache: Whether to read from and write to the on-disk cache.
                Caching is only applied when ``normalize`` is also ``True``.
                Defaults to ``True``.

        Returns:
            LoadedDataset containing the DataFrame, resolved dataset type, and
            absolute source path.

        Raises:
            LoaderError: If the file does not exist or cannot be parsed.

        Example:
            >>> loader = DataLoader()
            >>> ds = loader.load("data/site_a.csv", dataset_type="co2")
            >>> ds.df.head()
        """
        try:
            dataset_type = DatasetType(dataset_type)
        except ValueError as e:
            raise LoaderError(f"Invalid dataset_type: {e}") from e

        if use_cache:
            ensure_dir(self.cache_dir)
            if self.verbose:
                logger.info(f"Cache dir: {self.cache_dir}")

        file_path = Path(file_path)

        if not file_path.exists():
            raise LoaderError(f"File not found: {file_path}")

        # Try to load from cache first
        if use_cache and normalize:
            try:
                cached_df = self._load_from_cache(file_path)
                if cached_df is not None:
                    return LoadedDataset(
                        df=cached_df,
                        dataset_type=dataset_type,
                        source_path=file_path.absolute(),
                    )
            except CacheError:
                # Cache miss or invalid, continue to load from source
                if self.verbose:
                    logger.info(f"Cache miss for {file_path}. Loading from source.")
                pass

        # Load from source file
        try:
            df = self._load_csv(file_path)

            # Normalize if requested
            if normalize:
                df = self._normalize(df)

                # Save to cache for next time
                if use_cache:
                    try:
                        self._save_to_cache(file_path, df)
                    except CacheError:
                        # Cache save failed, but we have the data so continue
                        logger.warning(f"Failed to save cache in: {file_path}")
                        pass

            return LoadedDataset(
                df=df,
                dataset_type=dataset_type,
                source_path=file_path.absolute(),
            )

        except Exception as e:
            raise LoaderError(f"Failed to load {file_path}: {e}") from e

    def _load_csv(self, file_path: Path) -> pd.DataFrame:
        """Load a CSV file with automatic TOA5 format detection.

        First attempts to parse the file as a Campbell Scientific TOA5 file
        (skipping the header, units, and sampling rows). Falls back to a
        standard CSV read if that attempt fails.  The ``TIMESTAMP`` column is
        promoted to the DataFrame index when present.

        Args:
            file_path: Path to the CSV file to load.

        Returns:
            DataFrame with ``TIMESTAMP`` as the index.

        Raises:
            Exception: Propagates any unhandled read error from the fallback
                CSV parse.

        Example:
            >>> loader = DataLoader()
            >>> df = loader._load_csv(Path("data/site_a.dat"))
            >>> df.index.name
            'TIMESTAMP'
        """
        # Try to detect if this is a TOA5 file (Campbell Scientific format)
        # TOA5 files have 4 header rows before data
        try:
            # First attempt: assume TOA5 format
            df = pd.read_csv(
                file_path,
                skiprows=[0, 2, 3],  # Skip header, units, sampling rows
                parse_dates=["TIMESTAMP"],
                na_values=["NAN", "NaN", ""],
                low_memory=False,
            )
        except (pd.errors.ParserError, ValueError, KeyError):
            logger.info("File is not TOA5 file. Load as standart CSV.")
            # Fallback: try standard CSV
            df = pd.read_csv(
                file_path,
                parse_dates=["TIMESTAMP"],
                na_values=["NAN", "NaN", ""],
                low_memory=False,
            )

        # Set TIMESTAMP as index
        if "TIMESTAMP" in df.columns.tolist():
            df = df.set_index("TIMESTAMP")
        elif "Timestamp" in df.columns:
            df = df.rename(columns={"Timestamp": "TIMESTAMP"})
            df = df.set_index("TIMESTAMP")

        if self.verbose:
            logger.info(f"Loaded from {file_path}")

        return df

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replace NAN sentinel strings with ``np.nan`` and coerce numeric columns.

        Replaces the string values ``"NAN"``, ``"NaN"``, and ``""`` with
        ``np.nan``, then attempts ``pd.to_numeric`` conversion on every column
        whose dtype is ``object``.

        Args:
            df: DataFrame to normalize.

        Returns:
            Normalized DataFrame with numeric dtypes where possible.

        Example:
            >>> import pandas as pd
            >>> loader = DataLoader()
            >>> raw = pd.DataFrame({"CO2": ["1.2", "NAN", "3.4"]})
            >>> loader._normalize(raw)["CO2"].isna().sum()
            1
        """
        if self.verbose:
            logger.info("Normalizing empty strings to np.nan ...")

        # Replace "NAN" strings with actual NaN
        df = df.replace(["NAN", "NaN", ""], np.nan)

        # Convert numeric columns
        for col in df.columns:
            if df[col].dtype == "object":
                try:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                except Exception as e:
                    logger.warning(f"Failed to normalize {col}: {e}")
                    pass

        if self.verbose:
            logger.info("DataFrame normalized.")

        return df

    @staticmethod
    def _get_cache_key(file_path: Path) -> str:
        """Generate a cache key from the absolute file path and its mtime.

        The key is an MD5 hex digest of ``"<absolute_path>_<mtime>"``, so it
        changes automatically whenever the source file is modified.

        Args:
            file_path: Path to the source file.

        Returns:
            Hex-encoded MD5 digest string used as the cache filename stem.

        Example:
            >>> key = DataLoader._get_cache_key(Path("data/site_a.csv"))
            >>> len(key)
            32
        """
        mtime = file_path.stat().st_mtime
        key_string = f"{file_path.absolute()}_{mtime}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Resolve the on-disk path for a given cache key.

        Args:
            cache_key: Hex digest string returned by ``_get_cache_key``.

        Returns:
            Absolute path to the ``.pkl`` cache file inside ``cache_dir``.

        Example:
            >>> loader = DataLoader(cache_dir="/tmp/cache")
            >>> loader._get_cache_path("abc123")
            PosixPath('/tmp/cache/abc123.pkl')
        """
        return self.cache_dir / f"{cache_key}.pkl"

    def _load_from_cache(self, file_path: Path) -> pd.DataFrame | None:
        """Load a DataFrame from cache if the cache entry is still valid.

        Validates the cached entry by comparing the stored mtime against the
        current mtime of ``file_path``.  Stale or corrupted cache files are
        deleted automatically.

        Args:
            file_path: Absolute path to the original source file.

        Returns:
            Cached DataFrame when a valid entry exists, ``None`` on a cache
            miss or stale entry.

        Raises:
            CacheError: If the cache file exists but cannot be deserialized.

        Example:
            >>> loader = DataLoader()
            >>> df = loader._load_from_cache(Path("data/site_a.csv"))
            >>> df is None  # cache miss on first run
            True
        """
        cache_key = self._get_cache_key(file_path)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            cached_data = joblib.load(cache_path)

            if self.verbose:
                logger.info(f"Loaded from cache: {cache_path}")

            # Validate cache metadata
            if isinstance(cached_data, dict):
                df = cached_data.get("dataframe")
                metadata = cached_data.get("metadata", {})

                # Check if cache is still valid
                if metadata.get("mtime") == file_path.stat().st_mtime:
                    return df

            # Cache is invalid
            cache_path.unlink(missing_ok=True)
            return None

        except Exception as e:
            # Cache is corrupted, delete it
            cache_path.unlink(missing_ok=True)
            raise CacheError(f"Cache read failed: {e}") from e

    def _save_to_cache(self, file_path: Path, df: pd.DataFrame) -> None:
        """Persist a DataFrame to the on-disk cache.

        Stores the DataFrame alongside metadata (absolute path and mtime) so
        that ``_load_from_cache`` can validate the entry on subsequent reads.
        The file is compressed at level 3 via ``joblib``.

        Args:
            file_path: Absolute path to the original source file.
            df: Normalized DataFrame to cache.

        Raises:
            CacheError: If the cache file cannot be written.

        Example:
            >>> loader = DataLoader(cache_dir="/tmp/cache")
            >>> loader._save_to_cache(Path("data/site_a.csv"), df)
        """
        cache_key = self._get_cache_key(file_path)
        cache_path = self._get_cache_path(cache_key)

        try:
            cached_data = {
                "dataframe": df,
                "metadata": {
                    "file_path": str(file_path.absolute()),
                    "mtime": file_path.stat().st_mtime,
                },
            }

            joblib.dump(cached_data, cache_path, compress=3)

            if self.verbose:
                logger.info(f"Cache saved to {cache_path}.")

        except Exception as e:
            raise CacheError(f"Cache write failed: {e}") from e

    def clear_cache(self) -> int:
        """Delete all ``.pkl`` cache files from ``cache_dir``.

        Returns:
            Number of cache files successfully deleted.

        Example:
            >>> loader = DataLoader(cache_dir="/tmp/cache")
            >>> loader.clear_cache()
            3
        """
        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
                count += 1
            except Exception as e:
                logger.warning(f"Failed to delete cache file {cache_file}: {e}")

        if self.verbose:
            logger.info(f"Deleted {count} cache files.")

        return count
