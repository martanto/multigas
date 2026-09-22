"""DataFrame shaping helpers.

Thin wrappers over pandas used by :class:`multigas.core.query.Query` and the
loader:

- :func:`to_datetime_index` promotes a named column to a sorted
  :class:`pandas.DatetimeIndex`.
- :func:`to_dateime_index` — deprecated alias for :func:`to_datetime_index`
  (kept for backwards compatibility; do not use in new code).
- :func:`get_dates` returns the min/max index dates alongside their string
  representations.
- :func:`convert_to_wind_direction` maps a single compass bearing to its sector
  label using one of the ``WIND_DIRECTIONS_*`` tables in
  :mod:`multigas.core.constant`.
- :func:`convert_to_wind_quadrant` maps a single compass bearing to its
  quadrant label using one of the ``WIND_QUADRANTS_*`` tables in
  :mod:`multigas.core.constant`.
"""

from typing import Any

import pandas as pd

from multigas.core.constant import WIND_QUADRANTS_8
from multigas.core.exceptions import ValidationError
from multigas.utils.validation import validate_dataframe_column


def to_datetime_index(df: pd.DataFrame, index_col: str) -> pd.DataFrame:
    """Convert a column to pd.DatetimeIndex and set it as the DataFrame index.

    Args:
        df (pd.DataFrame): DataFrame containing the column to convert.
        index_col (str): Name of the column to use as the datetime index.

    Returns:
        pd.DataFrame: DataFrame sorted ascending with a pd.DatetimeIndex.

    Raises:
        ColumnError: If ``index_col`` does not exist in ``df`` (raised by
            :func:`multigas.utils.validation.validate_dataframe_column`).
        ValidationError: If the values of ``index_col`` cannot be parsed as
            datetimes by :func:`pandas.to_datetime`.

    Example:
        >>> df = pd.DataFrame({"time": ["2025-01-01"], "val": [1]})
        >>> result = to_datetime_index(df, "time")
        >>> isinstance(result.index, pd.DatetimeIndex)
        True
    """
    if isinstance(df.index, pd.DatetimeIndex):
        return df

    validate_dataframe_column(df, index_col)
    df = df.set_index(index_col)
    try:
        df.index = pd.to_datetime(df.index)
    except (ValueError, TypeError, pd.errors.ParserError) as e:
        raise ValidationError(
            f"Failed to convert column {index_col!r} to a DatetimeIndex: {e}"
        ) from e
    df = df.sort_index(ascending=True)
    return df


# Deprecated alias kept for backwards compatibility. New code should call
# :func:`to_datetime_index` — the original name was misspelled.
to_dateime_index = to_datetime_index


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


def convert_to_wind_direction(
    direction_degree: float,
    wind_directions: list[dict[str, Any]],
    as_code: bool = False,
) -> str | None:
    """Map a single compass bearing to its sector label.

    Bearings are normalised modulo 360 before lookup, so ``360.0``,
    ``720.0``, and negative values wrap to their correct sector.
    ``NaN`` inputs return ``None`` (they do not raise), which lets the
    caller preserve row alignment when mapping over a Series that may
    contain gaps.

    Args:
        direction_degree (float): The bearing in degrees. Values outside
            ``[0, 360)`` are normalised via modulo 360; ``NaN`` returns
            ``None``.
        wind_directions (list[dict[str, Any]]): Sector table to look
            ``direction_degree`` up in — one of
            :data:`multigas.core.constant.WIND_DIRECTIONS_4`,
            :data:`WIND_DIRECTIONS_8`, or :data:`WIND_DIRECTIONS_16`.
            Each entry must expose ``min_degree``, ``max_degree``,
            ``direction``, and ``code`` keys.
        as_code (bool): If ``True``, return the short compass code
            (``"N"``, ``"NE"``, …); otherwise the full name
            (``"North"``, ``"Northeast"``, …). Defaults to ``False``.

    Returns:
        str | None: The matching sector label, or ``None`` when the
            input is ``NaN``.

    Raises:
        ValidationError: If a finite bearing (after normalisation)
            falls outside every bin in ``wind_directions`` — indicates
            a bin-definition bug in the caller-supplied table.

    Example:
        >>> from multigas.core.constant import WIND_DIRECTIONS_8
        >>> convert_to_wind_direction(90, WIND_DIRECTIONS_8, as_code=True)
        'E'
        >>> convert_to_wind_direction(360.0, WIND_DIRECTIONS_8) == "North"
        True
    """
    if pd.isna(direction_degree):
        return None

    normalised = direction_degree % 360
    label_key = "code" if as_code else "direction"
    for wind_direction in wind_directions:
        if wind_direction["min_degree"] <= normalised < wind_direction["max_degree"]:
            return wind_direction[label_key]

    raise ValidationError(
        f"Wind direction {direction_degree} degrees could not be mapped "
        f"to any of the provided wind-direction bins."
    )


def convert_to_wind_quadrant(
    direction_degree: float,
    wind_quadrants: list[dict[str, Any]] | None = None,
    as_code: bool = False,
) -> str | None:
    """Map a single compass bearing to its quadrant label.

    Bearings are normalised modulo 360 before lookup, so ``360.0``,
    ``720.0``, and negative values wrap to their correct quadrant.
    ``NaN`` inputs return ``None`` (they do not raise), which lets the
    caller preserve row alignment when mapping over a Series that may
    contain gaps.

    Args:
        direction_degree (float): The bearing in degrees. Values outside
            ``[0, 360)`` are normalised via modulo 360; ``NaN`` returns
            ``None``.
        wind_quadrants (list[dict[str, Any]] | None): Quadrant table to
            look ``direction_degree`` up in — one of
            :data:`multigas.core.constant.WIND_QUADRANTS_4` or
            :data:`WIND_QUADRANTS_8`. Each entry must expose
            ``min_degree``, ``max_degree``, ``direction``, and ``code``
            keys. Defaults to
            :data:`multigas.core.constant.WIND_QUADRANTS_8` when
            ``None``.
        as_code (bool): If ``True``, return the short quadrant code
            (``"I"``, ``"II"``, …); otherwise the full name
            (``"Quadrant I"``, ``"Quadrant II"``, …). Defaults to
            ``False``.

    Returns:
        str | None: The matching quadrant label, or ``None`` when the
            input is ``NaN``.

    Raises:
        ValidationError: If a finite bearing (after normalisation)
            falls outside every bin in ``wind_quadrants`` — indicates
            a bin-definition bug in the caller-supplied table.

    Example:
        >>> from multigas.core.constant import WIND_QUADRANTS_4
        >>> convert_to_wind_quadrant(45, WIND_QUADRANTS_4, as_code=True)
        'I'
        >>> convert_to_wind_quadrant(200) == "Quadrant V"
        True
    """
    if pd.isna(direction_degree):
        return None

    if wind_quadrants is None:
        wind_quadrants = WIND_QUADRANTS_8

    normalised = direction_degree % 360
    label_key = "code" if as_code else "direction"
    for wind_quadrant in wind_quadrants:
        if wind_quadrant["min_degree"] <= normalised < wind_quadrant["max_degree"]:
            return wind_quadrant[label_key]

    raise ValidationError(
        f"Wind direction {direction_degree} degrees could not be mapped "
        f"to any of the provided wind-quadrant bins."
    )
