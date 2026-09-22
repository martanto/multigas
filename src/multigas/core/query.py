"""Fluent query interface for pandas DataFrames with a datetime index.

Defines :class:`Query`, the mixin that :class:`multigas.core.types.MultiGasData`
inherits from. It normalises the index to a :class:`pandas.DatetimeIndex`,
tracks the currently selected columns, and exposes chainable helpers for
column selection and null-checking.
"""

from typing import Any, Self

import numpy as np
import pandas as pd

from multigas.logging import logger
from multigas.core.constant import COMPARATOR
from multigas.core.exceptions import ColumnError
from multigas.utils.dataframe import get_dates, to_dateime_index
from multigas.utils.validation import check_columns_exist


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
    def missing_columns(self) -> list[str]:
        """Names of columns that contain at least one missing value.

        "Missing" is defined by :meth:`column_has_missing` — ``NaN``/``pd.NA``
        for every dtype and, for string-like dtypes, the empty string ``""``.
        When a selection is active (:attr:`selected_columns` non-empty), only
        selected columns are inspected; otherwise every column is checked.
        Mirrors the scoping of :attr:`empty_columns`.

        Returns:
            list[str]: Column names that have at least one missing value.

        Example:
            >>> q.missing_columns
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
        check_columns_exist(column_name, self.columns)
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
        check_columns_exist(column_name, self.columns)
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
            numeric_column_only: If ``True``, delegate to
                :meth:`select_numeric_columns` so that non-numeric names are
                dropped from the selection. A log line names the dropped
                columns when :attr:`verbose` is ``True``. Defaults to
                ``False``.
            validate: If ``True``, raise :class:`ColumnError` when any name is
                not present in :attr:`columns`. The exception lists every
                missing name in one message. Defaults to ``True``.

        Returns:
            Self for method chaining.

        Raises:
            ColumnError: When ``validate=True`` and one or more names are not
                in :attr:`columns`.

        Example:
            >>> q.select_columns(["CO2", "SO2"]).df.columns.tolist()
            ['CO2', 'SO2']
        """
        if isinstance(column_names, str):
            column_names = [column_names]

        if validate:
            check_columns_exist(column_names, self.columns)

        if numeric_column_only:
            return self.select_numeric_columns(column_names, validate=False)

        self.selected_columns = list(column_names)
        return self

    def select_numeric_columns(
        self,
        column_names: str | list[str] | None = None,
        validate: bool = True,
    ) -> Self:
        """Select numeric columns, optionally filtered to a given subset.

        When ``column_names`` is ``None``, all numeric columns in the DataFrame
        are selected. Otherwise, the selection is the intersection of
        ``column_names`` and :attr:`numeric_columns`; non-numeric names are
        dropped, and a log line names them when :attr:`verbose` is ``True``.

        Args:
            column_names: Column name(s) to filter. If ``None``, all numeric
                columns are selected. Defaults to ``None``.
            validate: If ``True``, raise :class:`ColumnError` when any name is
                not present in :attr:`columns` (non-numeric names that *do*
                exist are silently dropped by the intersection instead).
                Defaults to ``True``.

        Returns:
            Self for method chaining.

        Raises:
            ColumnError: When ``validate=True`` and one or more names are not
                in :attr:`columns`.

        Example:
            >>> q.select_numeric_columns().selected_columns
            ['CO2', 'SO2', 'H2S']
        """
        if column_names is None:
            self.selected_columns = list(self.numeric_columns)
            if self.verbose:
                logger.info(
                    f"Selected all {len(self.numeric_columns)} numeric "
                    f"column(s): {self.numeric_columns}"
                )
            return self

        if isinstance(column_names, str):
            column_names = [column_names]

        if validate:
            check_columns_exist(column_names, self.columns)

        numeric_selection = self.intersection(column_names, self.numeric_columns)
        self.selected_columns = numeric_selection

        if self.verbose:
            dropped = [c for c in column_names if c not in numeric_selection]
            if dropped:
                logger.info(
                    f"Dropped {len(dropped)} non-numeric "
                    f"column(s) from selection: {dropped}"
                )
            logger.info(
                f"Selected {len(numeric_selection)} numeric column(s) from "
                f"{len(column_names)} requested: {numeric_selection}"
            )

        return self

    def count(self) -> int:
        """Count length of dataframe

        Returns:
            int: Length of dataframe
        """
        return int(self.df.shape[0])

    def where(self, column_name: str, comparator: str, value: Any) -> Self:
        """Filter :attr:`df` in place by comparing a column against a value.

        Mutates :attr:`df` so subsequent operations see only the matching rows;
        the pristine :attr:`df_original` is untouched and can be restored via
        :meth:`refresh`. When ``column_name`` equals :attr:`index_col`, the
        comparison runs against the DatetimeIndex instead of a column.

        Args:
            column_name (str): Name of the column (or the index) to compare.
            comparator (str): Comparison operator. Must be one of
                :data:`multigas.core.constant.COMPARATOR` — English, symbolic,
                and Indonesian aliases are all accepted.
            value (Any): Right-hand side of the comparison.

        Returns:
            Self: The same instance, to allow method chaining.

        Raises:
            ValueError: When ``comparator`` is not in ``COMPARATOR``.
            ColumnError: When ``column_name`` is neither a known column nor
                the index name.

        Example:
            >>> q.where("CO2", ">", 1.0).count()
            42
        """
        if comparator not in COMPARATOR:
            raise ValueError(
                f"Invalid comparator: {comparator}. Use one of: {COMPARATOR}"
            )

        if column_name == self.df.index.name:
            df_column = self.df.index
        else:
            check_columns_exist(column_name, self.columns)
            df_column = self.df[column_name]

        if comparator in ["==", "like", "equal", "eq", "sama dengan"]:
            mask = df_column == value
        elif comparator in ["!=", "ne", "not equal", "tidak sama dengan"]:
            mask = df_column != value
        elif comparator in [
            ">",
            "gt",
            "greater than",
            "lebih besar",
            "lebih besar dari",
        ]:
            mask = df_column > value
        elif comparator in ["<", "lt", "less than", "kurang", "kurang dari"]:
            mask = df_column < value
        elif comparator in [
            ">=",
            "gte",
            "greater than equal",
            "lebih besar sama dengan",
        ]:
            mask = df_column >= value
        else:
            mask = df_column <= value

        self.df = self.df[mask]
        return self

    def where_date(self, date_str: str) -> Self:
        """Filter :attr:`df` in place to rows whose index falls within ``date_str``.

        Uses pandas partial-string slicing on the DatetimeIndex. A bare
        ``self.df.loc[date_str]`` collapses to a :class:`pandas.Series` when
        only one row matches (or when the index precision matches ``date_str``
        exactly), which would break every downstream :class:`Query` method
        that assumes :attr:`df` is a :class:`pandas.DataFrame`. Using the
        slice form ``self.df.loc[date_str:date_str]`` guarantees a
        :class:`pandas.DataFrame` regardless of how many rows match. Mutation
        is reversible via :meth:`refresh`.

        Args:
            date_str (str): Partial-string date accepted by pandas'
                DatetimeIndex slicing — e.g. ``"2025"``, ``"2025-01"``, or
                ``"2025-01-15"``. The bound is expanded to cover that whole
                year, month, or day.

        Returns:
            Self: The same instance, to allow method chaining.

        Example:
            >>> q.where_date("2025-01-15").count()
            1440
        """
        self.df = self.df.loc[date_str:date_str]
        return self

    def where_date_between(self, start_date: str, end_date: str) -> Self:
        """Filter :attr:`df` in place to rows whose index is between two dates.

        Uses pandas partial-string slicing on the DatetimeIndex, so both
        bounds are inclusive and each accepts any precision pandas supports
        (year, month, day). As with :meth:`where_date`, the slice form
        guarantees :attr:`df` stays a :class:`pandas.DataFrame`. Mutation is
        reversible via :meth:`refresh`.

        Args:
            start_date (str): Inclusive lower bound as a partial-string date
                — e.g. ``"2025"``, ``"2025-01"``, or ``"2025-01-15"``.
            end_date (str): Inclusive upper bound in the same partial-string
                format. The bound is expanded to cover the whole year, month,
                or day named.

        Returns:
            Self: The same instance, to allow method chaining.

        Example:
            >>> q.where_date_between("2025-01-01", "2025-01-31").count()
            44640
        """
        self.df = self.df.loc[start_date:end_date]
        return self

    def where_values_between(
        self,
        column_name: str,
        start_value: int | float,
        end_value: int | float,
    ) -> Self:
        """Filter :attr:`df` in place to rows where a column's value is in ``[start, end]``.

        Both bounds are inclusive. The named column must have a numeric
        dtype; non-numeric columns raise :class:`ColumnError` — use
        :meth:`where` for string or categorical comparisons. Mutation is
        reversible via :meth:`refresh`.

        Args:
            column_name (str): Name of the numeric column to filter on.
            start_value (int | float): Inclusive lower bound.
            end_value (int | float): Inclusive upper bound.

        Returns:
            Self: The same instance, to allow method chaining.

        Raises:
            ColumnError: When ``column_name`` is not a known column, or is
                not of a numeric dtype.

        Example:
            >>> q.where_values_between("CO2", 0.5, 1.5).count()
            128
        """
        check_columns_exist(column_name, self.columns)
        col = self.df[column_name]
        if not pd.api.types.is_numeric_dtype(col):
            raise ColumnError(
                f"Column '{column_name}' is not numeric (dtype={col.dtype}); "
                f"where_values_between requires a numeric column."
                f"Available numeric columns `{self.numeric_columns}`.`"
            )

        mask = col.between(start_value, end_value, inclusive="both")
        self.df = self.df[mask]
        return self

    def get(self) -> pd.DataFrame:
        """Narrow :attr:`df` to :attr:`selected_columns` and return it.

        When a selection is active, :attr:`df` is replaced with the
        column-projected frame and :attr:`numeric_columns` is recomputed to
        match. This is a *mutating* getter — the pruned columns leave
        :attr:`df` for good and can only be brought back via :meth:`refresh`,
        which restores from :attr:`df_original`. When no selection is active,
        :attr:`df` is returned unchanged.

        Returns:
            pd.DataFrame: The current working DataFrame, narrowed to
                :attr:`selected_columns` when a selection is active.

        Example:
            >>> q.select_columns(["CO2", "SO2"]).get().columns.tolist()
            ['CO2', 'SO2']
        """
        if not self.selected_columns:
            return self.df

        self.df = self.df[self.selected_columns]
        self.numeric_columns: list[str] = (
            self.df.select_dtypes(include=np.number).keys().tolist()
        )

        if self.verbose:
            logger.info(
                f"Narrowed dataframe to {len(self.selected_columns)} "
                f"selected column(s): {self.selected_columns}"
            )

        return self.df
