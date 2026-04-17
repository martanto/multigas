"""Data loading with caching and normalization."""

from pathlib import Path

import numpy as np
import joblib
import pandas as pd

from multigas.logging import logger
from multigas.core.types import DatasetType, LoadedDataset
from multigas.utils.path import ensure_dir
from multigas.utils.cache import get_cache_path
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
        (detected from the `TOA5` first-line marker and skipping the header,
        units, and sampling rows). Falls back to a standard CSV read if that
        attempt fails. The ``TIMESTAMP`` column is promoted to the DataFrame
        index when present.

        TOA5 header context (LoggerNet format):
            - Header row includes: file format type, station name, datalogger
              type, serial number, OS version, DLD name, DLD signature, and
              table name.
            - Next rows include field names, units, and processing descriptors.
            - Data rows are comma-separated records from a single table.
            - Optional ``TIMESTAMP`` and ``RECORD`` fields may be present.

        TOA5 format reference:
        https://help.campbellsci.com/loggernet-manual/ln_manual/campbell_scientific_file_formats/toa5.htm

        TOA5 example snippet:
            "TOA5","CR1000","CR1000","1031","CR1000.Std.00.60","CPU:Test.CR1","4062","Test"
            "TIMESTAMP","RECORD","batt_volt_Min","PTemp"
            "TS","RN","Volts","C"
            "","","Min","Smp"
            "2004-11-11 15:03:45",0,13.7,24.92
            "2004-11-11 15:04:00",1,13.7,24.95

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
        # TOA5 files have a format marker and 4 header rows before data.
        with file_path.open(mode="r", encoding="utf-8", errors="ignore") as source_file:
            first_line = source_file.readline()
        is_toa5 = first_line.startswith("TOA5")

        try:
            if is_toa5:
                df = pd.read_csv(
                    file_path,
                    skiprows=[0, 2, 3],  # Skip header, units, sampling rows
                    na_values=["NAN", "NaN", ""],
                    low_memory=False,
                )
            else:
                raise ValueError("Non-TOA5 source")
        except (pd.errors.ParserError, ValueError, KeyError):
            logger.info("File is not TOA5 file. Load as standart CSV.")
            df = pd.read_csv(
                file_path,
                na_values=["NAN", "NaN", ""],
                low_memory=False,
            )

        # Set TIMESTAMP as index
        timestamp_column = next(
            (
                column
                for column in df.columns
                if isinstance(column, str) and column.lower() == "timestamp"
            ),
            None,
        )
        if timestamp_column is not None:
            if timestamp_column != "TIMESTAMP":
                df = df.rename(columns={timestamp_column: "TIMESTAMP"})
            df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce")
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

        # Convert clearly numeric object columns only.
        for col in df.columns:
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(
                df[col]
            ):
                source = df[col]
                non_null_count = source.notna().sum()

                if non_null_count == 0:
                    continue

                converted = pd.to_numeric(source, errors="coerce")
                converted_non_null_count = converted.notna().sum()
                if converted_non_null_count == non_null_count:
                    df[col] = converted

        if self.verbose:
            logger.info("DataFrame normalized.")

        return df

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
        cache_path = get_cache_path(self.cache_dir, file_path)

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
                stat = file_path.stat()
                mtime_ns = metadata.get("mtime_ns")
                size = metadata.get("size")

                if mtime_ns is not None and size is not None:
                    if mtime_ns == stat.st_mtime_ns and size == stat.st_size:
                        return df
                elif metadata.get("mtime") == stat.st_mtime:
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
        cache_path = get_cache_path(self.cache_dir, file_path)

        try:
            cached_data = {
                "dataframe": df,
                "metadata": {
                    "file_path": str(file_path.absolute()),
                    "mtime": file_path.stat().st_mtime,
                    "mtime_ns": file_path.stat().st_mtime_ns,
                    "size": file_path.stat().st_size,
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
