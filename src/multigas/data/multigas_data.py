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

from typing import Self, Literal
from pathlib import Path

import pandas as pd

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
    ) -> list[ExtractedStats] | pd.DataFrame:
        """Split the working DataFrame by calendar day and write one CSV per day.

        Iterates every day between the first and last timestamp of
        :attr:`df` (inclusive), writing the rows for each day to
        ``<output_dir>/daily/<dataset_type>/<YYYY-MM-DD>.csv`` and
        collecting per-day stats: row count and completeness as a
        percentage in ``[0, 100]`` (computed by
        :func:`multigas.utils.dataframe.calculate_completeness` with
        ``as_percentage=True``, relative to the sampling interval
        implied by :attr:`dataset_type`). Days without data are
        recorded as ``total_data=0`` / ``completeness=0.0`` and the
        full list of missing days is logged at the end.

        Args:
            output_dir (Path | str | None): Destination root. When
                ``None``, files are written under ``<cwd>/output/``.
                Defaults to ``None``.
            return_as_list (bool): If ``True``, return the raw
                ``list[ExtractedStats]``; otherwise return a
                :class:`pandas.DataFrame` with columns ``date``,
                ``total_data``, ``completeness`` (percentage).
                Defaults to ``False``.

        Returns:
            list[ExtractedStats] | pd.DataFrame: Per-day stats, one
            entry per calendar day in the source range.
            ``completeness`` is a percentage in ``[0, 100]``.

        Example:
            >>> ds.extract_daily("exports/")
                     date  total_data  completeness
            0  2024-01-01        1440         100.0
            1  2024-01-02        1200         83.33
        """
        if output_dir is None:
            output_dir = Path.cwd() / "output"
        else:
            output_dir = Path(output_dir)

        daily_dir = output_dir / "daily" / self.dataset_type.value
        daily_dir.mkdir(parents=True, exist_ok=True)

        df = self.df.copy()
        dates = pd.date_range(
            df.index.min().normalize(),
            df.index.max().normalize(),
            freq="D",
        )

        extracted_files: list[ExtractedStats] = []
        missing_dates: list[str] = []
        for date in dates:
            date_str = date.strftime("%Y-%m-%d")
            output_file = daily_dir / f"{date_str}.csv"

            if self.verbose:
                logger.info(f"{date_str} :: Extracting ...")

            try:
                df_daily = df.loc[date_str]
            except KeyError:
                df_daily = df.iloc[0:0]

            if df_daily.empty:
                extracted_files.append(
                    ExtractedStats(date=date_str, total_data=0, completeness=0.0)
                )
                missing_dates.append(date_str)
                continue

            total_data = len(df_daily)
            extracted_files.append(
                ExtractedStats(
                    date=date_str,
                    total_data=total_data,
                    completeness=calculate_completeness(
                        total_data,
                        self.dataset_type,
                        as_percentage=True,
                    ),
                )
            )

            df_daily.to_csv(output_file, index=True)

            if self.verbose:
                logger.info(f"{date_str} :: Extracted to: {output_file}")

        if missing_dates:
            logger.warning(
                f"Found {len(missing_dates)} missing dates for file "
                f"{self.source_path}: {', '.join(missing_dates)}"
            )

        if return_as_list:
            return extracted_files

        return pd.DataFrame(extracted_files)

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
                / self.dataset_type.value
                / f"{self.source_path.stem}.csv"
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
                / self.dataset_type.value
                / f"{self.source_path.stem}.xlsx"
            )
        else:
            filepath = Path(path)

        if filepath.suffix != ".xlsx":
            filepath = filepath.with_suffix(".xlsx")

        filepath.parent.mkdir(parents=True, exist_ok=True)

        self.df.to_excel(filepath, index=True, engine="openpyxl")
        return str(filepath)
