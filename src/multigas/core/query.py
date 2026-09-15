"""Fluent query interface for pandas DataFrames with a datetime index.

Defines :class:`Query`, the mixin that :class:`multigas.core.types.MultiGasData`
inherits from. It normalises the index to a :class:`pandas.DatetimeIndex`,
tracks the currently selected columns, and exposes chainable helpers for
column selection and null-checking.
"""

from typing import Self

import numpy as np
import pandas as pd

from multigas.logging import logger
from multigas.utils.dataframe import get_dates, to_dateime_index
from multigas.utils.validation import validate_column


class Query:
    """Fluent column-selection and inspection wrapper around a DataFrame.

    Wraps a :class:`pandas.DataFrame`, promotes ``index_col`` to a
    :class:`pandas.DatetimeIndex`, and keeps a pristine copy in
    :attr:`df_original` so :meth:`refresh` can restore it. Column selection
    is stored in :attr:`selected_columns` and can be composed via
    :meth:`select_columns` and :meth:`select_numeric_columns`.

    Attributes:
        df (pd.DataFrame): Working DataFrame with a datetime index.
        df_original (pd.DataFrame): Untouched copy captured at construction.
        index_col (str): Column promoted to the datetime index.
        columns (list[str]): All column names in :attr:`df_original`.
        selected_columns (list[str]): Currently selected column names.
        numeric_columns (list[str]): Numeric-dtype columns in :attr:`df`.
        start_date (pd.Timestamp): Earliest timestamp in :attr:`df`.
        end_date (pd.Timestamp): Latest timestamp in :attr:`df`.
        start_date_str (str): :attr:`start_date` formatted as ``YYYY-MM-DD``.
        end_date_str (str): :attr:`end_date` formatted as ``YYYY-MM-DD``.
        verbose (bool): Whether operations emit informational log messages.

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame(
        ...     {"TIMESTAMP": ["2025-01-01"], "CO2": [1.2], "SO2": [0.3]}
        ... )
        >>> q = Query(df)
        >>> q.select_numeric_columns().selected_columns
        ['CO2', 'SO2']
    """

    def __init__(
        self,
        df: pd.DataFrame,
        index_col: str | None = None,
        verbose: bool = False,
    ):
        """Initialise Query with a DataFrame and a datetime index column.

        Args:
            df: DataFrame to wrap. Must contain ``index_col`` as a column or
                already have a :class:`pd.DatetimeIndex`.
            index_col: Column name to use as the datetime index. Defaults to
                ``"TIMESTAMP"``.
            verbose: Emit informational log messages for each operation.
                Defaults to ``False``.

        Example:
            >>> import pandas as pd
            >>> df = pd.DataFrame({"TIMESTAMP": ["2025-01-01"], "CO2": [1.2]})
            >>> q = Query(df)
            >>> isinstance(q.df.index, pd.DatetimeIndex)
            True
        """
        index_col: str = index_col or "TIMESTAMP"
        df = to_dateime_index(df, index_col)
        df_original: pd.DataFrame = df.copy()

        self.df: pd.DataFrame = df
        self.index_col: str = index_col

        self.df_original: pd.DataFrame = df_original
        self.columns: list[str] = df_original.columns.tolist()
        self.selected_columns: list[str] = []
        self.numeric_columns: list[str] = (
            df.select_dtypes(include=np.number).keys().tolist()
        )
        self.start_date, self.end_date, self.start_date_str, self.end_date_str = (
            get_dates(df)
        )

        self.verbose: bool = verbose

    @property
    def nan_columns(self) -> list[str]:
        """Names of columns that contain at least one NaN or empty string.

        When a selection is active (:attr:`selected_columns` non-empty), only
        selected columns are inspected; otherwise every column is checked.
        Mirrors the scoping of :attr:`empty_columns`.

        Returns:
            list[str]: Column names that have any NaN or empty-string value.

        Example:
            >>> q.nan_columns
            ['CO2', 'H2S']
        """
        columns_name = self.selected_columns or self.columns
        return [c for c in columns_name if self.column_has_missing(c)]

    @property
    def empty_columns(self) -> list[str]:
        """Names of columns whose values sum to zero (all-zero or all-empty).

        When a selection is active (:attr:`selected_columns` non-empty), only
        selected columns are inspected; otherwise every column is checked.

        Returns:
            list[str]: Column names that are considered empty.

        Example:
            >>> q.empty_columns
            ['unused_channel']
        """
        columns_name = self.columns
        columns_selected: int = len(self.selected_columns)
        empty_columns: list[str] = []

        if columns_selected > 0:
            columns_name = self.selected_columns

        for column_name in columns_name:
            if self.column_is_empty(column_name):
                empty_columns.append(column_name)

        return empty_columns

    @staticmethod
    def intersection(first_list: list[str], second_list: list[str]) -> list[str]:
        """Return elements of ``first_list`` that also appear in ``second_list``.

        Order is taken from ``first_list``; duplicates in ``first_list`` are
        preserved. Prefer this over :func:`set.intersection` when the caller
        needs the original ordering.

        Args:
            first_list (list[str]): Primary list; result order matches this list.
            second_list (list[str]): List whose membership is tested against.

        Returns:
            list[str]: Elements common to both lists, in ``first_list`` order.

        Example:
            >>> Query.intersection(["a", "b", "c"], ["b", "c", "d"])
            ['b', 'c']
        """
        intersect_list: list[str] = [
            value for value in first_list if value in second_list
        ]
        return intersect_list

    @staticmethod
    def unique(first_list: list[str], second_list: list[str]) -> list[str]:
        """Return the deduplicated union of two lists.

        Args:
            first_list (list[str]): First list of names.
            second_list (list[str]): Second list of names.

        Returns:
            list[str]: All distinct values from both inputs. Order is not
                guaranteed because a set is used internally.

        Example:
            >>> sorted(Query.unique(["a", "b"], ["b", "c"]))
            ['a', 'b', 'c']
        """
        return list(set(first_list + second_list))

    def reset_selected_columns(self) -> Self:
        """Clear the current column selection.

        Sets :attr:`selected_columns` back to an empty list. Emits a log line
        when :attr:`verbose` is ``True``.

        Returns:
            Self: The same instance, to allow method chaining.

        Example:
            >>> q.select_columns(["CO2"]).reset_selected_columns().selected_columns
            []
        """
        self.selected_columns: list[str] = []
        if self.verbose:
            logger.info("Selected columns resetted")
        return self

    def refresh(self) -> Self:
        """Restore :attr:`df` to the pristine :attr:`df_original` copy.

        Also clears the current selection and recomputes
        :attr:`numeric_columns` and the ``start_date`` / ``end_date`` pair.

        Returns:
            Self: The same instance, to allow method chaining.

        Example:
            >>> q.select_columns(["CO2"]).refresh().is_filtered()
            False
        """
        df = self.df_original.copy()

        self.df = df
        self.reset_selected_columns()
        self.numeric_columns: list[str] = (
            df.select_dtypes(include=np.number).keys().to_list()
        )
        self.start_date, self.end_date, self.start_date_str, self.end_date_str = (
            get_dates(df)
        )

        if self.verbose:
            logger.info("Dataframe resetted to original data")

        return self

    def is_filtered(self) -> bool:
        """Check whether :attr:`df` differs from :attr:`df_original`.

        Returns:
            bool: ``True`` when the working DataFrame no longer equals the
                pristine copy, ``False`` otherwise.

        Example:
            >>> q.is_filtered()
            False
        """
        return False if self.df_original.equals(self.df) else True

    def column_has_missing(self, column_name: str) -> bool:
        """Report whether a column contains any missing value.

        "Missing" covers ``NaN``/``pd.NA`` for every dtype and, for
        string-like dtypes, the empty string ``""``. The string check uses
        :func:`pandas.api.types.is_string_dtype` so it covers legacy
        ``object`` columns and pandas 3.x's default ``StringDtype``.
        ``fillna("")`` runs first so ``pd.NA`` does not propagate through
        the ``==`` comparison.

        Args:
            column_name (str): Name of the column to inspect.

        Returns:
            bool: ``True`` if the column has at least one NaN, ``pd.NA``, or
                (for string-like dtypes) empty string; ``False`` otherwise.

        Example:
            >>> q.column_has_missing("CO2")
            False
        """
        validate_column(column_name, self.columns)
        col = self.df[column_name]
        has_null = col.isna().to_numpy().any()
        has_empty = (
            col.fillna("").eq("").to_numpy().any()
            if pd.api.types.is_string_dtype(col)
            else False
        )
        return bool(has_null or has_empty)

    def column_is_empty(self, column_name: str) -> bool:
        """Report whether a column has no meaningful data.

        A column is treated as empty when every value is NaN, or — depending
        on dtype — additionally when every value is ``0`` (numeric) or ``""``
        (object). Non-numeric, non-object dtypes (e.g. datetime, boolean) are
        empty only when every value is NaN.

        Args:
            column_name (str): Name of the column to inspect.

        Returns:
            bool: ``True`` when the column is considered empty.

        Example:
            >>> q.column_is_empty("unused_channel")
            True
        """
        validate_column(column_name, self.columns)
        col = self.df[column_name]

        if col.isna().to_numpy().all():
            return True

        if pd.api.types.is_numeric_dtype(col):
            return bool(col.fillna(0).eq(0).to_numpy().all())

        if pd.api.types.is_string_dtype(col):
            return bool(col.fillna("").eq("").to_numpy().all())

        return False

    def select_columns(
        self,
        column_names: str | list[str],
        numeric_column_only: bool = False,
        validate: bool = True,
    ) -> Self:
        """Select one or more columns by name.

        Sets :attr:`selected_columns` to the given names. Optionally restricts
        the selection to numeric columns only.

        Args:
            column_names: A single column name or a list of column names to
                select.
            numeric_column_only: If ``True``, further filter the selection to
                numeric columns via :meth:`select_numeric_columns`. Defaults to
                ``False``.
            validate: Raise an error if any column name is not present in the
                DataFrame. Defaults to ``True``.

        Returns:
            Self for method chaining.

        Example:
            >>> q.select_columns(["CO2", "SO2"]).df.columns.tolist()
            ['CO2', 'SO2']
        """
        if isinstance(column_names, str):
            column_names = [column_names]

        if validate:
            for column_name in column_names:
                validate_column(column_name, self.columns)

        self.selected_columns: list[str] = column_names

        if numeric_column_only:
            self.select_numeric_columns(column_names, validate=False)

        return self

    def select_numeric_columns(
        self,
        column_names: str | list[str] | None = None,
        validate: bool = True,
    ) -> Self:
        """Select numeric columns, optionally filtered to a given subset.

        When ``column_names`` is ``None``, all numeric columns in the DataFrame
        are selected. Otherwise, the selection is the intersection of
        ``column_names`` and :attr:`numeric_columns`.

        Args:
            column_names: Column name(s) to filter. If ``None``, all numeric
                columns are selected. Defaults to ``None``.
            validate: Validate each name against the DataFrame columns before
                filtering. Defaults to ``True``.

        Returns:
            Self for method chaining.

        Example:
            >>> q.select_numeric_columns().selected_columns
            ['CO2', 'SO2', 'H2S']
        """
        if column_names is None:
            self.selected_columns = self.numeric_columns
            return self

        if isinstance(column_names, str):
            column_names = [column_names]

        if validate:
            for column_name in column_names:
                validate_column(column_name, self.columns)

        self.selected_columns: list[str] = self.intersection(
            column_names, self.numeric_columns
        )

        if self.verbose:
            logger.info(
                f"Total numeric columns: {len(self.numeric_columns)}. {self.numeric_columns}"
            )

        return self
