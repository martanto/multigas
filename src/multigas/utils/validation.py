import pandas as pd

from multigas.logging import logger


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
        if len(inconsistent_data) > 0:
            logger.warning("\nInconsistent time differences:")
            logger.warning(time_diffs[inconsistent_mask].describe())

    return is_consistent, consistent_data, inconsistent_data, sampling_rate


def validate_columns(
    df: pd.DataFrame, columns: list[str], exclude_columns: list[str] | None = None
) -> None:
    """Validate that specified columns exist in DataFrame.

    Checks that all specified columns exist in the DataFrame, except those in
    the exclude list. Raises ValueError with detailed message if any column is missing.

    Args:
        df (pd.DataFrame): DataFrame to validate.
        columns (list[str]): List of column names to validate.
        exclude_columns (list[str] | None, optional): List of column names to skip
            validation. Defaults to None.

    Returns:
        None

    Raises:
        ValueError: If any column in columns (except exclude_columns) does not exist
            in the DataFrame.

    Examples:
        >>> df = pd.DataFrame({"rsam_f0": [1, 2], "rsam_f1": [3, 4]})
        >>> validate_columns(df, ["rsam_f0", "rsam_f1"])  # No error
        >>> validate_columns(df, ["rsam_f2"])  # Raises ValueError
    """
    excluded = set(exclude_columns or [])
    available = set(df.columns.tolist())
    missing_columns = [
        column
        for column in columns
        if column not in excluded and column not in available
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}. "
            f"Available columns: {df.columns.tolist()}"
        )


def column_is_exists(df: pd.DataFrame, column: str) -> None:
    """Log an error if a column does not exist in the DataFrame.

    Args:
        df (pd.DataFrame): DataFrame to inspect.
        column (str): Column name to look up.

    Returns:
        None

    Raises:
        ValueError: If ``column`` is not present in ``df``.

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({"a": [1, 2]})
        >>> column_is_exists(df, "a")  # no error
    """

    columns: list[str] = df.columns.tolist()
    if column not in columns:
        logger.error(
            f"`{column}` is not a valid column name. Available columns: {columns}"
        )
