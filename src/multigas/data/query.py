from typing import Self

import numpy as np
import pandas as pd

from multigas.logging import logger
from multigas.utils.dataframe import get_dates, to_dateime_index
from multigas.utils.validation import validate_column


class Query:
    """Extends pandas dataframe fluent query

    Attributes:
        df (pandas.DataFrame): Normalized pandas dataframe with datetime index.
        df_original (pandas.DataFrame): Original dataframe with datetime index.
        index_col (str): Column name for datetime index.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        index_col: str | None = None,
        drop_empty_columns: bool = False,
        verbose: bool = False,
    ):
        index_col: str = index_col or "TIMESTAMP"
        df = to_dateime_index(df, index_col)
        df_original: pd.DataFrame = df.copy()

        self.df: pd.DataFrame = df
        self.index_col: str = index_col
        self.drop_empty_columns: bool = drop_empty_columns

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
        """Columns with nan values

        Returns:
            list[str]: Columns with nan values
        """
        nan_columns: list[str] = []
        for column in self.columns:
            if self.column_has_nan(column):
                nan_columns.append(column)

        return nan_columns

    @property
    def empty_columns(self) -> list[str]:
        """Columns with empty values

        Returns:
            list[str]: Columns with nan or empty values
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
        """Get intersection of two lists

        Args:
            first_list (list[str]): first list
            second_list (list[str]): second list

        Returns:
            list[str]: Intersection of two lists
        """
        intersect_list: list[str] = [
            value for value in first_list if value in second_list
        ]
        return intersect_list

    @staticmethod
    def unique(first_list: list[str], second_list: list[str]) -> list[str]:
        """Get unique values of two lists

        Args:
            first_list (list[str]): first list
            second_list (list[str]): second list

        Returns:
            list[str]: Unique values of two lists
        """
        return list(set(first_list + second_list))

    def reset_selected_columns(self) -> Self:
        """Reset selected columns

        Returns:
            Self: self
        """
        self.selected_columns: list[str] = []
        if self.verbose:
            logger.info("Selected columns resetted")
        return self

    def refresh(self) -> Self:
        """Return attributes with the original one

        Returns:
            Self
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
        """Check if data is filtered

        Returns:
            bool: True if data is filtered
        """
        return False if self.df_original.equals(self.df) else True

    def column_has_nan(self, column_name: str) -> bool:
        """Check if column has NULL or NaN value.

        Args:
            column_name (str): column name

        Returns:
            bool: True if column is empty
        """
        validate_column(column_name, self.columns)
        col = self.df[column_name]
        has_null = col.isna().to_numpy().any()
        has_empty = (col == "").any() if col.dtype == object else False
        return bool(has_null or has_empty)

    def column_is_empty(self, column_name: str) -> bool:
        """Check if column is empty.

        Args:
            column_name (str): column name

        Returns:
            bool: True if column is empty
        """
        validate_column(column_name, self.columns)
        return True if (self.df[column_name].sum() == 0) else False

    def select_columns(
        self,
        column_names: str | list[str],
        numeric_column_only: bool = False,
        validate: bool = True,
    ) -> Self:
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
        self, column_names: str | list[str] | None = None, validate: bool = True
    ) -> Self:
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
