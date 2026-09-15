"""DataFrame shaping helpers.

Thin wrappers over pandas used by :class:`multigas.core.query.Query` and the
loader:

- :func:`to_dateime_index` promotes a named column to a sorted
  :class:`pandas.DatetimeIndex`.
- :func:`get_dates` returns the min/max index dates alongside their string
  representations.
"""

import pandas as pd

from multigas.utils.validation import validate_dataframe_column


def to_dateime_index(df: pd.DataFrame, index_col: str) -> pd.DataFrame:
    """Convert a column to pd.DatetimeIndex and set it as the DataFrame index.

    Args:
        df (pd.DataFrame): DataFrame containing the column to convert.
        index_col (str): Name of the column to use as the datetime index.

    Returns:
        pd.DataFrame: DataFrame sorted ascending with a pd.DatetimeIndex.

    Raises:
        ValueError: If ``index_col`` does not exist in ``df``.

    Example:
        >>> df = pd.DataFrame({"time": ["2025-01-01"], "val": [1]})
        >>> result = to_dateime_index(df, "time")
        >>> isinstance(result.index, pd.DatetimeIndex)
        True
    """
    if isinstance(df.index, pd.DatetimeIndex):
        return df

    validate_dataframe_column(df, index_col)
    df = df.set_index(index_col)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index(ascending=True)
    return df


def get_dates(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp, str, str]:
    """Return the start date and end dates from a DataFrame's DatetimeIndex.

    Args:
        df (pd.DataFrame): DataFrame with a pd.DatetimeIndex.

    Returns:
        tuple[pd.Timestamp, pd.Timestamp, str, str]: A four-element tuple of
            ``(start_date, end_date, start_date_str, end_date_str)`` where the
            string values are formatted as ``"YYYY-MM-DD"``.

    Raises:
        TypeError: If the DataFrame index is not a pd.DatetimeIndex.

    Example:
        >>> import pandas as pd
        >>> idx = pd.date_range("2025-01-01", periods=3, freq="D")
        >>> df = pd.DataFrame({"val": [1, 2, 3]}, index=idx)
        >>> _, _, start_str, end_str = get_dates(df)
        >>> start_str, end_str
        ('2025-01-01', '2025-01-03')
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(
            f"DataFrame does not have a DatetimeIndex. Got {type(df.index)} instead."
        )

    start_date: pd.Timestamp = df.index.min()
    end_date: pd.Timestamp = df.index.max()
    start_date_str: str = start_date.strftime("%Y-%m-%d")
    end_date_str: str = end_date.strftime("%Y-%m-%d")

    return start_date, end_date, start_date_str, end_date_str
