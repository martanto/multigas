"""Validation helpers for DataFrames and column names.

Provides two families of checks used across the package:

- Sampling-rate validation via :func:`check_sampling_consistency`, which
  splits a DataFrame into consistent / inconsistent slices based on a
  target frequency and tolerance.
- Column-existence validation via :func:`check_columns_exist` (takes an
  explicit ``available`` list) and :func:`validate_dataframe_column`
  (DataFrame-aware wrapper around it). Both hard-fail via
  :class:`ColumnError`.
"""

import pandas as pd

from multigas.logging import logger
from multigas.core.exceptions import ColumnError


def check_sampling_consistency(
    df: pd.DataFrame,
    expected_freq: str = "10min",
    tolerance: str | None = None,
    verbose: bool = False,
) -> tuple[bool, pd.DataFrame, pd.DataFrame, int | None]:
    """Check sampling rate consistency and identify inconsistencies.

    Validates that a DataFrame has consistent time intervals between consecutive rows.
    Identifies and separates rows with inconsistent sampling rates based on tolerance.
    This is crucial for ensuring data quality in tremor time series.

    Args:
        df (pd.DataFrame): DataFrame with pd.DatetimeIndex.
        expected_freq (str, optional): Expected sampling frequency (e.g., "10min", "1H").
            Defaults to "10min".
        tolerance (str | None, optional): Tolerance for considering sampling periods as
            equal (e.g., "1min", "30s"). If None, no tolerance is applied and intervals
            must match exactly. Defaults to None.
        verbose (bool, optional): If True, print detailed information about inconsistencies.
            Defaults to False.

    Returns:
        tuple[bool, pd.DataFrame, pd.DataFrame, int | None]: Tuple containing:
            - is_consistent (bool): True if all samples are consistent, False otherwise.
            - consistent_data (pd.DataFrame): DataFrame with consistent samples only.
            - inconsistent_data (pd.DataFrame): DataFrame with inconsistent samples.
            - sampling_rate (int | None): Sampling rate in seconds if consistent, None otherwise.

    Raises:
        ValueError: If DataFrame has fewer than 2 rows.
        TypeError: If DataFrame index is not DatetimeIndex.

    Examples:
        >>> df = pd.DataFrame({"value": [1, 2, 3]},
        ...                   index=pd.date_range("2025-01-01", periods=3, freq="10min"))
        >>> is_consistent, consistent, inconsistent, rate = check_sampling_consistency(df)
        >>> print(is_consistent)
        True
    """
    if len(df) < 2:
        raise ValueError(
            "DataFrame must have at least 2 rows to check sampling consistency"
        )
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("DataFrame index must be DatetimeIndex")

    df = df.sort_index()
    sampling_rate = None

    time_diffs = df.index.to_series().diff()
    expected_diff = pd.Timedelta(expected_freq)

    if tolerance is None:
        inconsistent_mask: pd.Series = time_diffs != expected_diff
    else:
        tolerance_diff = pd.Timedelta(tolerance)
        lower_bound = expected_diff - tolerance_diff
        upper_bound = expected_diff + tolerance_diff
        inconsistent_mask = ~((time_diffs >= lower_bound) & (time_diffs <= upper_bound))
    inconsistent_mask.iloc[0] = False

    inconsistent_data = df[inconsistent_mask]
    consistent_data = df[~inconsistent_mask]
    is_consistent = inconsistent_data.empty

    if is_consistent:
        sampling_rate = int((df.index[1] - df.index[0]).total_seconds())

    if verbose:
        logger.info(f"Total rows: {len(df)}")
        logger.info(f"Inconsistent rows found: {len(inconsistent_data)}")
        logger.info(f"Consistent rows: {len(consistent_data)}")
        logger.info(f"Sampling rate: {sampling_rate}s")
        if len(inconsistent_data) > 0:
            logger.warning("\nInconsistent time differences:")
            logger.warning(time_diffs[inconsistent_mask].describe())

    return is_consistent, consistent_data, inconsistent_data, sampling_rate


def check_columns_exist(column_names: str | list[str], available: list[str]) -> None:
    """Ensure every given column name exists in a list of available names.

    Accepts a single name or a list. On failure raises :class:`ColumnError`
    once, listing every missing name and the full ``available`` set in the
    message. :class:`ColumnError` auto-logs via
    :meth:`MultigasException.__init__`, so callers do not need a manual
    ``logger.error(...)`` before this raise.

    Args:
        column_names (str | list[str]): Column name or names to look up.
        available (list[str]): Reference list of columns that exist.

    Raises:
        ColumnError: If one or more names are absent from ``available``.

    Example:
        >>> check_columns_exist("CO2", ["CO2", "SO2"])  # no error
        >>> check_columns_exist(["CO2", "H2S"], ["CO2", "SO2"])
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.ColumnError: Column(s) not found: ['H2S']. Available: ['CO2', 'SO2']
    """
    if isinstance(column_names, str):
        column_names = [column_names]

    missing = [c for c in column_names if c not in available]
    if missing:
        raise ColumnError(f"Column(s) not found: {missing}. Available: {available}")


def validate_dataframe_column(df: pd.DataFrame, column: str) -> None:
    """Ensure column exists in provided dataframe.

    Thin wrapper around :func:`check_columns_exist`, so a missing column
    raises :class:`ColumnError` (auto-logged).

    Args:
        df (pd.DataFrame): DataFrame to inspect.
        column (str): Column name to look up.

    Returns:
        None

    Raises:
        ColumnError: If ``column`` is not present in ``df``.

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"a": [1, 2]})
        >>> validate_dataframe_column(df, "a")  # no error
    """
    check_columns_exist(column, df.columns.tolist())
