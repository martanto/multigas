"""Container class for a loaded multi-gas dataset.

Defines :class:`MultiGasData`, a wrapper that pairs a loaded (and optionally
normalised) :class:`pandas.DataFrame` with its provenance metadata
(:class:`DatasetType` and source path) and inherits from
:class:`multigas.core.query.Query` so the fluent column-selection, filtering,
and wind-analysis helpers can be called directly on the dataset.

Example:
    >>> from multigas import read_file
    >>> ds = read_file("data/site_a.dat", dataset_type="1min")
    >>> ds.select_numeric_columns().df.head()
"""

import os
import json
from typing import Self, Literal
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed
from slugify import slugify

from multigas.logging import logger
from multigas.core.query import Query
from multigas.core.types import DatasetType, ExtractedStats
from multigas.core.constant import (
    WIND_QUADRANTS_4,
    WIND_QUADRANTS_8,
    WIND_DIRECTIONS_4,
    WIND_DIRECTIONS_8,
    WIND_DIRECTIONS_16,
)
from multigas.utils.dataframe import (
    count_csv_rows,
    calculate_completeness,
    convert_to_wind_quadrant,
    convert_to_wind_direction,
)
from multigas.utils.validation import check_columns_exist


class MultiGasData(Query):
    """A loaded DataFrame together with its provenance metadata and query capabilities.

    Extends :class:`Query` to expose fluent column-selection and filtering
    methods directly on the loaded dataset.

    Attributes:
        df (pd.DataFrame): The loaded (and optionally normalized) DataFrame.
        dataset_type (DatasetType): The type of dataset as declared by the caller.
        source_path (Path): Absolute path to the original source file.
        index_col (str): Column name used as the datetime index.
        verbose (bool): Whether to emit log messages for each operation.

    Example:
        >>> result = loader.load(path, DatasetType.ONE_MINUTE)
        >>> result.select_numeric_columns().df.head()
        >>> result.dataset_type
        <DatasetType.ONE_MINUTE: '1min'>
    """

    def __init__(
        self,
        df: pd.DataFrame,
        dataset_type: DatasetType,
        source_path: Path,
        index_col: str = "TIMESTAMP",
        verbose: bool = False,
    ):
        """Initialise the wrapper and delegate DataFrame setup to :class:`Query`.

        Args:
            df (pd.DataFrame): The loaded DataFrame.
            dataset_type (DatasetType): Dataset type declared by the caller.
            source_path (Path): Absolute path to the source file.
            index_col (str): Column to promote to the datetime index. Defaults
                to ``"TIMESTAMP"``.
            verbose (bool): Emit informational log messages for each operation.
                Defaults to ``False``.

        Example:
            >>> result = MultiGasData(df, DatasetType.ONE_MINUTE, path)
            >>> result.numeric_columns  # populated by Query.__init__
        """
        super().__init__(df, index_col, verbose)
        self.basename = source_path.stem
        self.basename_slug = slugify(self.basename)
        self.dataset_type: DatasetType = dataset_type
        self.source_path: Path = source_path

    def __repr__(self) -> str:
        """Return a concise string representation of the dataset.

        Returns:
            str: A string showing dataset_type, source_path, and DataFrame shape.

        Example:
            >>> repr(result)
            "MultiGasData(dataset_type=<DatasetType.ONE_MINUTE: '1min'>, ..., index_col='TIMESTAMP', verbose=False)"
        """
        return (
            f"MultiGasData("
            f"dataset_type={self.dataset_type!r}, "
            f"source_path={self.source_path!r}, "
            f"shape={self.df.shape}, "
            f"index_col={self.index_col!r}, "
            f"verbose={self.verbose!r})"
        )

    def add_wind_direction(
        self,
        wind_direction_column_name: str,
        as_code: bool = False,
        direction_to_use: Literal[16, 8, 4] = 16,
    ) -> Self:
        """Append a ``wind_direction`` column derived from a bearings column.

        Reads compass bearings (in degrees) from
        ``wind_direction_column_name`` and writes the corresponding
        compass-sector label into a new ``wind_direction`` column. The
        circle is divided into 4, 8, or 16 sectors depending on
        ``direction_to_use``. Bearings are normalised modulo 360 first,
        so ``360.0`` maps to North and negative values wrap correctly;
        ``NaN`` inputs produce ``None`` (no row is dropped).

        Args:
            wind_direction_column_name (str): Name of the source column
                holding bearings in degrees.
            as_code (bool): If ``True``, emit short codes (``"N"``,
                ``"NE"``, …); otherwise the full name (``"North"``,
                ``"Northeast"``, …). Defaults to ``False``.
            direction_to_use (Literal[16, 8, 4]): Number of compass
                sectors. Defaults to ``16``.

        Raises:
            ColumnError: If ``wind_direction_column_name`` is not
                present on the underlying DataFrame.
            ValidationError: If a finite bearing cannot be mapped to any
                sector — indicates a bin-definition bug in
                :mod:`multigas.core.constant`.

        Returns:
            Self: The same instance, for fluent chaining.

        Example:
            >>> result.add_wind_direction("WD_deg", direction_to_use=8)
            >>> result.df["wind_direction"].head()
        """
        check_columns_exist(wind_direction_column_name, self.df.columns.to_list())

        if direction_to_use == 16:
            _wind_directions = WIND_DIRECTIONS_16
        elif direction_to_use == 8:
            _wind_directions = WIND_DIRECTIONS_8
        else:
            _wind_directions = WIND_DIRECTIONS_4

        self.df["wind_direction"] = self.df[wind_direction_column_name].map(
            lambda deg: convert_to_wind_direction(
                deg, _wind_directions, as_code=as_code
            )
        )

        return self

    def add_wind_quadrant(
        self,
        wind_direction_column_name: str,
        as_code: bool = False,
        quadrant_to_use: Literal[8, 4] = 8,
    ) -> Self:
        """Append a ``wind_quadrant`` column derived from a bearings column.

        Reads compass bearings (in degrees) from
        ``wind_direction_column_name`` and writes the corresponding
        quadrant label into a new ``wind_quadrant`` column. The circle
        is divided into 4 or 8 quadrants depending on
        ``quadrant_to_use``. Bearings are normalised modulo 360 first,
        so ``360.0`` maps to the first quadrant and negative values
        wrap correctly; ``NaN`` inputs produce ``None`` (no row is
        dropped).

        Args:
            wind_direction_column_name (str): Name of the source column
                holding bearings in degrees.
            as_code (bool): If ``True``, emit short codes (``"I"``,
                ``"II"``, …); otherwise the full name (``"Quadrant I"``,
                ``"Quadrant II"``, …). Defaults to ``False``.
            quadrant_to_use (Literal[8, 4]): Number of quadrants.
                Defaults to ``8``.

        Raises:
            ColumnError: If ``wind_direction_column_name`` is not
                present on the underlying DataFrame.
            ValidationError: If a finite bearing cannot be mapped to any
                quadrant — indicates a bin-definition bug in
                :mod:`multigas.core.constant`.

        Returns:
            Self: The same instance, for fluent chaining.

        Example:
            >>> result.add_wind_quadrant("WD_deg", quadrant_to_use=4)
            >>> result.df["wind_quadrant"].head()
        """
        check_columns_exist(wind_direction_column_name, self.df.columns.to_list())

        if quadrant_to_use == 8:
            _wind_quadrants = WIND_QUADRANTS_8
        else:
            _wind_quadrants = WIND_QUADRANTS_4

        self.df["wind_quadrant"] = self.df[wind_direction_column_name].map(
            lambda deg: convert_to_wind_quadrant(deg, _wind_quadrants, as_code=as_code)
        )

        return self

    def extract_daily(
        self,
        output_dir: Path | str | None = None,
        return_as_list: bool = False,
        n_jobs: int = 1,
        overwrite: bool = True,
    ) -> list[ExtractedStats] | pd.DataFrame:
        """Split the working DataFrame by calendar day and write one CSV per day.

        Iterates every day between the first and last timestamp of
        :attr:`df` (inclusive), writing the rows for each day to
        ``<output_dir>/daily/<dataset_type_label>/<source_stem>/<YYYY-MM-DD>.csv``
        (where ``dataset_type_label`` is :attr:`DatasetType.label` —
        the hyphenated form such as ``"one-minute"``) and collecting
        per-day stats: row count and completeness as a percentage in
        ``[0, 100]`` (computed by
        :func:`multigas.utils.dataframe.calculate_completeness` with
        ``as_percentage=True``, relative to the sampling interval
        implied by :attr:`dataset_type`). Days without data are
        recorded as ``total_data=0`` / ``completeness=0.0`` and the
        full list of missing days is logged at the end.

        Alongside the per-day CSVs, the aggregated stats are also
        persisted under ``<output_dir>/daily/<dataset_type_label>/``:

        * When ``return_as_list=False`` (the default), the stats are
          written to ``<source_stem>.xlsx`` via
          :meth:`pandas.DataFrame.to_excel` (``openpyxl`` engine).
        * When ``return_as_list=True``, the raw
          ``list[ExtractedStats]`` is written to ``<source_stem>.json``
          via :func:`json.dump` with ``indent=4`` and
          ``ensure_ascii=False``.

        When ``n_jobs > 1``, per-day extraction runs in parallel via
        :class:`joblib.Parallel` with the ``loky`` backend. The
        effective worker count is capped at
        ``max(1, os.cpu_count() - 2)``. Result order is preserved,
        so the returned per-day stats stay date-ordered. Per-day
        ``verbose`` info logs are suppressed in workers to avoid
        interleaved multi-process output; the aggregated
        missing-days warning is still emitted once at the end.

        When ``overwrite=False``, days whose CSV already exists
        under ``<output_dir>/daily/<dataset_type_label>/`` are left
        alone — their row is instead reconstructed from the file's
        line count via :func:`count_csv_rows` (so the returned
        per-day shape stays intact). The count reflects the file on
        disk, not the current in-memory :attr:`df` (relevant if a
        caller has narrowed the frame via, e.g.,
        ``where_date_between``).

        Args:
            output_dir (Path | str | None): Destination root. When
                ``None``, files are written under ``<cwd>/output/``.
                Defaults to ``None``.
            return_as_list (bool): If ``True``, return the raw
                ``list[ExtractedStats]`` and persist it as
                ``<source_stem>.json``; otherwise return a
                :class:`pandas.DataFrame` with columns ``date``,
                ``total_data``, ``completeness`` (percentage) and
                persist it as ``<source_stem>.xlsx``. Defaults to
                ``False``.
            n_jobs (int): Number of parallel workers. ``1`` (the
                default) runs sequentially. Values ``> 1`` are
                capped at ``max(1, os.cpu_count() - 2)`` and
                dispatched to :class:`joblib.Parallel` with the
                ``loky`` backend.
            overwrite (bool): When ``True`` (the default), every
                per-day CSV is (re)written, replacing any existing
                file. When ``False``, days whose CSV already exists
                are left alone and their stats are read back from
                the file via :func:`count_csv_rows`.

        Returns:
            list[ExtractedStats] | pd.DataFrame: Per-day stats, one
            entry per calendar day in the source range.
            ``completeness`` is a percentage in ``[0, 100]``.

        Example:
            >>> ds.extract_daily("exports/")
                     date  total_data  completeness
            0  2024-01-01        1440         100.0
            1  2024-01-02        1200         83.33
            >>> ds.extract_daily("exports/", return_as_list=True)  # writes .json
            >>> ds.extract_daily("exports/", n_jobs=4)  # parallel
            >>> ds.extract_daily("exports/", overwrite=False)  # incremental
        """
        if output_dir is None:
            output_dir = Path.cwd() / "output"
        else:
            output_dir = Path(output_dir)

        dataset_dir = output_dir / "daily" / self.dataset_type.label
        daily_dir = dataset_dir / self.basename_slug
        daily_dir.mkdir(parents=True, exist_ok=True)

        df = self.df.copy()
        dates = pd.date_range(
            df.index.min().normalize(),
            df.index.max().normalize(),
            freq="D",
        )

        if n_jobs > 1:
            max_jobs = max(1, (os.cpu_count() or 1) - 2)
            n_jobs = min(n_jobs, max_jobs)

        jobs = MultiGasData._build_jobs(dates, df, daily_dir, overwrite)

        if n_jobs == 1:
            results = [
                MultiGasData._extract_one_day(
                    date_str,
                    df_daily,
                    output_file,
                    self.dataset_type,
                    verbose=self.verbose,
                    overwrite=job_overwrite,
                )
                for date_str, df_daily, output_file, job_overwrite in jobs
            ]
        else:
            results = Parallel(n_jobs=n_jobs, backend="loky")(
                delayed(MultiGasData._extract_one_day)(
                    date_str,
                    df_daily,
                    output_file,
                    self.dataset_type,
                    verbose=self.verbose,
                    overwrite=job_overwrite,
                )
                for date_str, df_daily, output_file, job_overwrite in jobs
            )

        skipped_count = sum(1 for _, _, _, job_overwrite in jobs if not job_overwrite)
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} existing files under {daily_dir}")

        extracted_files: list[ExtractedStats] = []
        missing_dates: list[str] = []
        for stats, is_missing in results:
            extracted_files.append(stats)
            if is_missing:
                missing_dates.append(stats["date"])

        if missing_dates:
            logger.warning(
                f"Found {len(missing_dates)} missing dates for file {self.source_path}"
            )
            logger.warning(f"Missing files: {', '.join(missing_dates)}")

        if return_as_list:
            json_path = dataset_dir / f"{self.basename_slug}.json"
            with open(json_path, "w", encoding="utf-8") as file:
                json.dump(extracted_files, file, indent=4, ensure_ascii=False)
            return extracted_files

        df_results = pd.DataFrame(extracted_files)
        df_results.to_csv(
            dataset_dir / f"{self.basename_slug}-completeness.csv", index=False
        )
        return df_results

    @staticmethod
    def _build_jobs(
        dates: pd.DatetimeIndex,
        df: pd.DataFrame,
        daily_dir: Path,
        overwrite: bool,
    ) -> list[tuple[str, pd.DataFrame, Path, bool]]:
        """Pre-slice the working DataFrame into per-day extraction jobs.

        Each job is a ``(date_str, df_daily, output_file,
        overwrite)`` tuple that :meth:`_extract_one_day` can consume
        without needing access to ``self`` (which is why this is a
        :func:`staticmethod`). Pre-slicing here — rather than
        passing the full ``df`` and a date into each worker — keeps
        the pickle payload sent to each :class:`joblib.Parallel`
        worker small: only the per-day slice travels over the pipe.
        Missing days come back as an empty DataFrame from the
        ``df.loc[date_str:date_str]`` slice — no exception is
        raised — and :meth:`_extract_one_day` handles them via
        the ``.empty`` check.

        When the caller passes ``overwrite=False`` and the target
        CSV already exists, the job's per-tuple ``overwrite`` flag
        is set to ``False`` and the frame slot is filled with a bare
        ``pd.DataFrame()`` sentinel: the day will be skipped by
        :meth:`_extract_one_day` (which reads stats back from the
        existing file), and no per-day slice is paid for or
        pickled to a worker.

        Args:
            dates (pd.DatetimeIndex): Calendar days to iterate over.
            df (pd.DataFrame): Working DataFrame (a copy of
                :attr:`df`) indexed by a :class:`pd.DatetimeIndex`.
            daily_dir (Path): Directory into which each day's CSV
                will be written.
            overwrite (bool): Caller-level overwrite flag. When
                ``False``, days whose target CSV already exists
                get a "don't write" job (per-tuple flag ``False``,
                empty placeholder frame); every other day gets a
                normal "write" job (per-tuple flag ``True``).

        Returns:
            list[tuple[str, pd.DataFrame, Path, bool]]: One job per
                date in ``dates``, in the same order. The last
                field is the per-job overwrite decision.

        Example:
            >>> jobs = MultiGasData._build_jobs(
            ...     dates, ds.df.copy(), out_dir, overwrite=True
            ... )
            >>> jobs[0][0]
            '2024-01-01'
        """
        jobs: list[tuple[str, pd.DataFrame, Path, bool]] = []
        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            output_file = daily_dir / f"{date_str}.csv"
            if not overwrite and output_file.exists():
                jobs.append((date_str, pd.DataFrame(), output_file, False))
            else:
                df_daily = df.loc[date_str:date_str]
                jobs.append((date_str, df_daily, output_file, True))
        return jobs

    @staticmethod
    def _extract_one_day(
        date_str: str,
        df_daily: pd.DataFrame,
        output_file: Path,
        dataset_type: DatasetType,
        verbose: bool,
        overwrite: bool,
    ) -> tuple[ExtractedStats, bool]:
        """Extract one day's rows to CSV and return its per-day stats.

        Shared by the sequential and parallel branches of
        :meth:`extract_daily`. Kept as a :func:`staticmethod` so it
        can be dispatched by :class:`joblib.Parallel` without
        pickling ``self`` — the loky worker only receives the
        arguments explicitly passed here.

        When ``overwrite=False``, the write is skipped and stats
        are reconstructed from the existing CSV via
        :func:`count_csv_rows` (line count minus header). This
        branch is reached only when :meth:`_build_jobs` already
        confirmed the file exists, so the CSV read is safe.

        Args:
            date_str (str): Calendar day formatted as ``YYYY-MM-DD``.
            df_daily (pd.DataFrame): Rows for this day. An empty
                frame signals either a missing day (when
                ``overwrite=True``) — which triggers the
                ``total_data=0`` / ``completeness=0.0`` return —
                or a placeholder for a skipped write (when
                ``overwrite=False``).
            output_file (Path): Target CSV path.
            dataset_type (DatasetType): Dataset sampling interval,
                forwarded to :func:`calculate_completeness`.
            verbose (bool): Emit per-day info logs. Callers pass
                ``False`` in the parallel branch to keep multi-process
                log output tidy.
            overwrite (bool): When ``True``, write ``df_daily`` to
                ``output_file`` (overwriting any existing file).
                When ``False``, skip the write and read stats back
                from ``output_file`` via :func:`count_csv_rows`.

        Returns:
            tuple[ExtractedStats, bool]: The per-day stats and a
                ``is_missing`` flag (``True`` when ``df_daily`` was
                empty and ``overwrite=True``, ``False`` otherwise).

        Example:
            >>> MultiGasData._extract_one_day(
            ...     "2024-01-01", df_daily, path, DatasetType.ONE_MINUTE,
            ...     verbose=False, overwrite=True,
            ... )
            (ExtractedStats(date='2024-01-01', total_data=1440, ...), False)
        """
        if not overwrite:
            if verbose:
                logger.info(
                    f"{date_str} :: Already exists, reading stats from: {output_file}"
                )
            total_data = count_csv_rows(output_file)
            return (
                ExtractedStats(
                    date=date_str,
                    total_data=total_data,
                    completeness=calculate_completeness(
                        total_data,
                        dataset_type,
                        as_percentage=True,
                    ),
                ),
                False,
            )

        if verbose:
            logger.info(f"{date_str} :: Extracting ...")

        if df_daily.empty:
            return (
                ExtractedStats(date=date_str, total_data=0, completeness=0.0),
                True,
            )

        total_data = len(df_daily)
        stats = ExtractedStats(
            date=date_str,
            total_data=total_data,
            completeness=calculate_completeness(
                total_data,
                dataset_type,
                as_percentage=True,
            ),
        )
        df_daily.to_csv(output_file, index=True)

        if verbose:
            logger.info(f"{date_str} :: Extracted to: {output_file}")

        return stats, False

    def to_csv(self, path: str | None = None) -> str:
        """Write the working DataFrame to a CSV file.

        When ``path`` is omitted, the file is written to
        ``<cwd>/output/csv/<dataset_type>/<source_stem>.csv``. Any
        explicit ``path`` is used verbatim, with a ``.csv`` suffix
        appended when missing. The parent directory is created on
        demand.

        Args:
            path (str | None): Destination path. When ``None``, the file
                is written under ``<cwd>/output/csv/<dataset_type>/``
                using the source file's stem. Defaults to ``None``.

        Returns:
            str: String representation of the written file path.

        Example:
            >>> ds.to_csv()
            '.../output/csv/1min/site_a.csv'
            >>> ds.to_csv("exports/custom_name.csv")
            'exports/custom_name.csv'
        """
        if path is None:
            filepath = (
                Path.cwd()
                / "output"
                / "csv"
                / self.basename_slug
                / f"{self.basename}.csv"
            )
        else:
            filepath = Path(path)

        if filepath.suffix != ".csv":
            filepath = filepath.with_suffix(".csv")

        filepath.parent.mkdir(parents=True, exist_ok=True)

        self.df.to_csv(filepath, index=True)
        return str(filepath)

    def to_excel(self, path: str | None = None) -> str:
        """Write the working DataFrame to an Excel (``.xlsx``) file.

        When ``path`` is omitted, the file is written to
        ``<cwd>/output/excel/<dataset_type>/<source_stem>.xlsx``. Any
        explicit ``path`` is used verbatim, with a ``.xlsx`` suffix
        appended when missing. The parent directory is created on
        demand. Excel writing uses the ``openpyxl`` engine (a core
        runtime dependency).

        Args:
            path (str | None): Destination path. When ``None``, the file
                is written under ``<cwd>/output/excel/<dataset_type>/``
                using the source file's stem. Defaults to ``None``.

        Returns:
            str: String representation of the written file path.

        Example:
            >>> ds.to_excel()
            '.../output/excel/1min/site_a.xlsx'
            >>> ds.to_excel("exports/custom_name.xlsx")
            'exports/custom_name.xlsx'
        """
        if path is None:
            filepath = (
                Path.cwd()
                / "output"
                / "excel"
                / self.basename_slug
                / f"{self.basename}.xlsx"
            )
        else:
            filepath = Path(path)

        if filepath.suffix != ".xlsx":
            filepath = filepath.with_suffix(".xlsx")

        filepath.parent.mkdir(parents=True, exist_ok=True)

        self.df.to_excel(filepath, index=True, engine="openpyxl")
        return str(filepath)
