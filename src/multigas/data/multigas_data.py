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

from multigas.core.query import Query
from multigas.core.types import DatasetType
from multigas.core.constant import (
    WIND_QUADRANTS_4,
    WIND_QUADRANTS_8,
    WIND_DIRECTIONS_4,
    WIND_DIRECTIONS_8,
    WIND_DIRECTIONS_16,
)
from multigas.utils.dataframe import (
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
            lambda deg: convert_to_wind_quadrant(
                deg, _wind_quadrants, as_code=as_code
            )
        )

        return self
