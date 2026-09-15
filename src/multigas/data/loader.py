"""Data loading with caching and normalisation.

Home of :class:`DataLoader`, the full-control entry point for reading
Campbell Scientific TOA5 or plain CSV files into a
:class:`multigas.core.types.MultiGasData`. Loading is a three-step pipeline:

1. Cache lookup (skipped when ``overwrite=True`` or ``normalize=False``).
2. On-disk read — TOA5 auto-detection first, plain CSV as fallback.
3. Optional normalisation (NaN-sentinel replacement, numeric coercion,
   optional empty-column drop) followed by cache write.

For a one-call convenience wrapper see :func:`multigas.core.io.read_file`.
"""

from pathlib import Path

import numpy as np
import joblib
import pandas as pd

from multigas.logging import logger
from multigas.core.types import DatasetType, MultiGasData
from multigas.utils.path import ensure_dir
from multigas.utils.cache import save_cache, get_cache_path
from multigas.core.exceptions import LoaderError


class DataLoader:
    """File I/O, normalisation, and cache management for multi-gas datasets.

    Reads TOA5 or plain CSV files, optionally normalises them (NaN sentinels
    replaced, numeric coercion, empty-column drop) and serialises the result
    to an on-disk joblib cache keyed by absolute path + mtime.

    Attributes:
        basename (str | None): ``file_path.stem`` of the most recent load,
            used for naming the normalised CSV.
        output_dir (Path): Root output directory (``<cwd>/output``).
        normalize_dir (Path): Where normalised CSV copies are written.
        cache_dir (Path): Directory holding ``.pkl`` cache entries.
        overwrite (bool): Skip the cache lookup on the next :meth:`load` call.
        verbose (bool): Emit informational log messages during loading.

    Example:
        >>> loader = DataLoader(cache_dir="output/cache", verbose=True)
        >>> dataset = loader.load("data/site_a.dat", dataset_type="1min")
        >>> dataset.dataset_type
        <DatasetType.ONE_MINUTE: '1min'>
    """

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        overwrite: bool = False,
        verbose: bool = False,
    ):
        """Configure paths, caching behaviour, and verbosity.

        Args:
            cache_dir (Path | str | None): Directory that will hold cache
                entries. Defaults to ``<cwd>/output/cache`` when ``None``.
            overwrite (bool): If ``True``, subsequent :meth:`load` calls
                ignore any existing cache entry and reload from source.
                Defaults to ``False``.
            verbose (bool): Emit informational log messages during loading.
                Defaults to ``False``.

        Example:
            >>> loader = DataLoader()
            >>> loader_custom = DataLoader(cache_dir="/tmp/cache", verbose=True)
        """
        output_dir = Path.cwd() / "output"

        if cache_dir is None:
            cache_dir = output_dir / "cache"

        self.basename: str | None = None
        self.output_dir: Path = output_dir
        self.normalize_dir: Path = output_dir / "normalized"
        self.cache_dir: Path = Path(cache_dir)
        self.overwrite: bool = overwrite
        self.verbose: bool = verbose

    def load(
        self,
        file_path: Path | str,
        dataset_type: DatasetType | str,
        drop_empty_columns: bool = False,
        normalize: bool = True,
        use_cache: bool = True,
    ) -> MultiGasData:
        """Load a file into a :class:`MultiGasData`, with optional caching.

        Attempts to serve from cache when both ``use_cache`` and ``normalize``
        are ``True`` and ``self.overwrite`` is ``False``. On a cache miss the
        file is read from disk, optionally normalised, and the result is
        written back to the cache.

        Args:
            file_path (Path | str): Path to the source CSV / TOA5 file.
            dataset_type (DatasetType | str): Dataset type identifier — a
                :class:`DatasetType` member or its string value
                (e.g. ``"1min"``).
            drop_empty_columns (bool): Drop columns that are entirely NaN
                after normalisation. Only applied when ``normalize`` is
                ``True``. Defaults to ``False``.
            normalize (bool): Replace NaN-sentinel strings with ``np.nan``
                and coerce object columns to numeric. Defaults to ``True``.
            use_cache (bool): Read from and write to the on-disk cache.
                Caching only applies when ``normalize`` is also ``True``.
                Defaults to ``True``.

        Returns:
            MultiGasData: Wraps the loaded DataFrame, resolved
                :class:`DatasetType`, and absolute source path.

        Raises:
            LoaderError: If ``dataset_type`` is invalid, the file is missing,
                or the source cannot be parsed.

        Example:
            >>> loader = DataLoader()
            >>> ds = loader.load("data/site_a.dat", dataset_type="1min")
            >>> ds.df.head()
        """
        try:
            dataset_type = DatasetType(dataset_type)
        except ValueError as e:
            raise LoaderError(f"Invalid dataset_type: {e}") from e

        file_path = Path(file_path)
        if not file_path.exists():
            raise LoaderError(f"File not found: {file_path}")

        self.basename = file_path.stem

        if use_cache and not self.overwrite:
            ensure_dir(self.cache_dir)
            if self.verbose:
                logger.info(f"Cache dir: {self.cache_dir}")

        # Try to load from cache first. `_load_from_cache` returns None on
        # any soft failure (miss, stale, or corrupted), so no exception
        # handling is needed here.
        if use_cache and normalize and not self.overwrite:
            cached_df = self._load_from_cache(file_path)
            if cached_df is not None:
                return MultiGasData(
                    df=cached_df,
                    dataset_type=dataset_type,
                    source_path=file_path.absolute(),
                )
            elif self.verbose:
                logger.info(f"Cache miss for {file_path}. Loading from source.")

        # Load from source file
        try:
            df = self._load_csv(file_path)

            # Normalize if requested
            if normalize:
                df = self._normalize(df, drop_empty_columns=drop_empty_columns)
                if use_cache:
                    save_cache(df, file_path, self.cache_dir, verbose=self.verbose)

            return MultiGasData(
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
        is_toa5 = first_line.split(",")[0].strip('"') == "TOA5"

        try:
            if is_toa5:
                df = pd.read_csv(
                    file_path,
                    skiprows=[0, 2, 3],  # Skip header, units, sampling rows
                    na_values=["NAN", "NaN", "", "0"],
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

    def _normalize(
        self, df: pd.DataFrame, drop_empty_columns: bool = False
    ) -> pd.DataFrame:
        """Replace NAN sentinel strings with ``np.nan`` and coerce numeric columns.

        Replaces the string values ``"NAN"``, ``"NaN"``, and ``""`` with
        ``np.nan``, then attempts ``pd.to_numeric`` conversion on every column
        whose dtype is ``object``.

        Args:
            df: DataFrame to normalize.
            drop_empty_columns: If ``True``, drop columns that are entirely NaN
                after normalization and log how many were removed.

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
            logger.info("Normalizing data ...")

        # Replace "NAN" strings with actual NaN
        df = df.replace(["NAN", "NaN", ""], np.nan)

        # Drop rows where RECORD is missing, then cast to integer
        if "RECORD" in df.columns:
            df = df.dropna(subset=["RECORD"])
            df["RECORD"] = df["RECORD"].astype(int)

        # Convert clearly numeric object columns only.
        for index, _ in enumerate(df.columns):
            source = df.iloc[:, index]
            if pd.api.types.is_object_dtype(source) or pd.api.types.is_string_dtype(
                source
            ):
                non_null_count = int(source.notna().sum())

                if non_null_count == 0:
                    continue

                converted = pd.to_numeric(source, errors="coerce")
                converted_series = pd.Series(converted, index=source.index)
                converted_non_null_count = int(converted_series.notna().sum())
                if converted_non_null_count == non_null_count:
                    df.isetitem(index, converted_series.to_numpy())

        if drop_empty_columns:
            before = len(df.columns)
            df = df.dropna(axis=1, how="all")
            dropped = before - len(df.columns)
            logger.info(f"Dropped {dropped} empty column(s).")

        ensure_dir(self.normalize_dir)
        normalized_path = self.normalize_dir / f"{self.basename}.csv"
        df.to_csv(normalized_path)

        if self.verbose:
            logger.info(f"Saved normalized file to {normalized_path}")

        return df

    def _load_from_cache(self, file_path: Path) -> pd.DataFrame | None:
        """Load a DataFrame from cache if the cache entry is still valid.

        Validates the cached entry by comparing the stored mtime against the
        current mtime of ``file_path``. Stale or corrupted cache files are
        deleted automatically. A corrupted cache is a soft failure — the
        method logs a warning, removes the bad file, and returns ``None`` so
        the caller can transparently reload from source.

        Args:
            file_path: Absolute path to the original source file.

        Returns:
            Cached DataFrame when a valid entry exists, ``None`` on a cache
            miss, stale entry, or corrupted cache file.

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
            if self.verbose:
                logger.info(f"Loading from cache: {cache_path}")

            cached_data = joblib.load(cache_path)

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

            if self.verbose:
                logger.warning(f"Cache invalid: {cache_path}")

            return None

        except Exception as e:
            # Corrupted cache is a soft failure: delete the bad file, warn,
            # and return None so the caller falls back to reloading from
            # source without treating it as a real error.
            cache_path.unlink(missing_ok=True)
            logger.warning(f"Cache invalid, will reload: {cache_path} ({e})")
            return None
