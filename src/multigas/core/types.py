"""Shared type aliases, enums, and dataclasses for the multigas package.

Groups the small, dependency-light types that would otherwise be scattered
across the package:

- Type aliases: :data:`DateLike`, :data:`ColumnName`, :data:`Comparator`.
- Enums: :class:`DatasetType`, :class:`LogLevel`, :class:`SensorStatus`,
  :class:`FileFormat`.
- TypedDicts: :class:`DatasetMetadataDict`, :class:`ExtractedStats`.

The :class:`~multigas.data.multigas_data.MultiGasData` container that pairs
a loaded DataFrame with its provenance lives alongside the loader in
:mod:`multigas.data.multigas_data`.

Values for :class:`DatasetType` are chosen so that they double as pandas
frequency aliases where applicable (``"1s"``, ``"2s"``, ``"6h"``, ``"1min"``).
"""

from enum import IntEnum, StrEnum, EnumMeta
from typing import TypedDict
from datetime import datetime

import pandas as pd


DateLike = str | datetime | pd.Timestamp
"""Anything that :func:`pandas.to_datetime` can interpret as a single date."""

ColumnName = str
"""Alias for a DataFrame column name; kept explicit for readability."""

Comparator = str
"""Alias for a comparison operator string (e.g. ``">="``, ``"=="``)."""


def _raise_missing_value(cls: EnumMeta, value: object) -> None:
    """Raise a descriptive ValueError for an unrecognised enum value.

    Args:
        cls: The enum class that rejected the value.
        value: The value that failed to match any member.

    Raises:
        ValueError: Always raised with a message listing valid values and
            attribute-access forms.

    Example:
        >>> _raise_missing_value(DatasetType, "bad")
        ValueError: 'bad' is not a valid DatasetType. ...
    """
    values = ", ".join(f"`{m.value}`" for m in cls)  # ty:ignore[unresolved-attribute]
    attrs = ", ".join(f"`{cls.__name__}.{m.name}`" for m in cls)  # ty:ignore[unresolved-attribute]
    raise ValueError(
        f"{value!r} is not a valid {cls.__name__}. Valid values: {values} or {attrs}"
    )


class DatasetType(StrEnum):
    """Sampling interval or acquisition mode of a multi-gas dataset.

    Members whose value is a pandas frequency alias correspond to the four
    fixed sampling rates emitted by the datalogger. The remaining members
    (:attr:`ZERO`, :attr:`SPAN`, :attr:`WX`) tag calibration and weather
    streams that are read side-by-side with the sample data.

    Example:
        >>> DatasetType("1min")
        <DatasetType.ONE_MINUTE: '1min'>
        >>> DatasetType.SIX_HOURS.value
        '6h'
    """

    ONE_SECOND = "1s"
    TWO_SECONDS = "2s"
    SIX_HOURS = "6h"
    ONE_MINUTE = "1min"
    ZERO = "zero"
    SPAN = "span"
    WX = "wx"

    @classmethod
    def _missing_(cls, value: object) -> None:
        """Raise a descriptive error for unrecognised values.

        Args:
            value: The value that failed to match any member.

        Raises:
            ValueError: Always raised with a message listing valid string
                values and attribute-access forms.

        Example:
            >>> DatasetType("bad")
            ValueError: 'bad' is not a valid DatasetType. ...
        """
        _raise_missing_value(cls, value)

    @property
    def label(self) -> str:
        """Human-readable, hyphenated label for this dataset type.

        Returns a lowercase hyphenated form suitable for use as a
        directory or file-name segment (e.g. ``"one-minute"``,
        ``"six-hour"``). Sampling-interval members return the spelled-out
        cadence; categorical members (:attr:`SPAN`, :attr:`WX`) fall
        back to their raw string value so this property is safe to call
        on every member of the enum.

        This is deliberately named ``label`` rather than ``name`` to
        avoid shadowing :attr:`enum.Enum.name`, which every enum member
        already provides and which the package relies on internally
        (e.g. in :func:`_raise_missing_value`).

        Returns:
            str: A human-readable label such as ``"one-minute"``.

        Example:
            >>> DatasetType.ONE_MINUTE.label
            'one-minute'
            >>> DatasetType.SIX_HOURS.label
            'six-hour'
            >>> DatasetType.SPAN.label
            'span'
        """
        _labels: dict[str, str] = {
            "1s": "one-second",
            "2s": "two-second",
            "1min": "one-minute",
            "6h": "six-hour",
            "zero": "zero",
        }
        return _labels.get(self.value, self.value)

    @property
    def total_data(self) -> int:
        """Expected number of records per day for this dataset type.

        Returns:
            int: Count of records a complete 24-hour acquisition should
            contain at this sampling rate.

        Raises:
            ValueError: If the member has no defined daily count (currently
                :attr:`SPAN` and :attr:`WX`, which are categorical streams
                without a fixed per-day cadence).

        Example:
            >>> DatasetType.ONE_SECOND.total_data
            86400
            >>> DatasetType.SIX_HOURS.total_data
            4
        """
        _totals: dict[str, int] = {
            "1s": 86400,
            "2s": 5760,
            "1min": 1440,
            "6h": 4,
            "zero": 4,
        }
        if self.value not in _totals:
            raise ValueError(
                f"{self!r} has no defined total_data; only "
                f"{', '.join(f'`{k}`' for k in _totals)} are supported."
            )

        return _totals[self.value]


class DatasetMetadataDict(TypedDict, total=False):
    """Metadata extracted from a Campbell Scientific TOA5 header.

    All keys are optional; only those present in the source file are populated.

    Attributes:
        station: Station name recorded by the datalogger.
        logger_type: Datalogger model (e.g. ``"CR1000"``).
        firmware: Firmware / OS build identifier.
        program_name: Name of the CRBasic program producing the table.
        file_sampling: Sampling declaration recorded in the file header.
        serial_number: Datalogger serial number.
        os_version: Operating-system version string reported by the logger.

    Example:
        >>> meta: DatasetMetadataDict = {"station": "SiteA", "logger_type": "CR1000"}
        >>> meta["station"]
        'SiteA'
    """

    station: str
    logger_type: str
    firmware: str
    program_name: str
    file_sampling: str
    serial_number: str
    os_version: str


class LogLevel(StrEnum):
    """Verbosity levels understood by the package logger.

    Values are lowercased strings so they can be passed straight to loguru
    without additional coercion.

    Example:
        >>> LogLevel.INFO
        <LogLevel.INFO: 'info'>
        >>> LogLevel("debug").value
        'debug'
    """

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class SensorStatus(IntEnum):
    """Campbell Scientific multi-gas sensor operational status codes.

    Each member maps a numeric status code reported by the datalogger to a
    human-readable description of the sensor's current operating mode.

    Example:
        >>> SensorStatus(-2)
        <SensorStatus.CHEMICAL_SENSOR_OFF: -2>
        >>> SensorStatus(1).name
        'SAMPLE_ACQUISITION'
        >>> SensorStatus(4).description
        'Standart Gas Measurement for CO2 and SO2'
    """

    CHEMICAL_SENSOR_OFF = -2
    WARMING_UP = -1
    ZERO = 0
    SAMPLE_ACQUISITION = 1
    SPAN_CO2_SO2 = 4
    SPAN_H2S = 6
    MANUAL_ZERO = 10
    MANUAL_SAMPLE = 11
    MANUAL_SPAN_CO2_SO2 = 14
    MANUAL_SPAN_H2S = 16

    @classmethod
    def _missing_(cls, value: object) -> None:
        """Raise a descriptive error for unrecognised status codes.

        Args:
            value: The value that failed to match any member.

        Raises:
            ValueError: Always raised with a message listing valid integer
                values and attribute-access forms.

        Example:
            >>> SensorStatus(99)
            ValueError: 99 is not a valid SensorStatus. ...
        """
        _raise_missing_value(cls, value)

    @property
    def description(self) -> str:
        """Human-readable description of this status code.

        Returns:
            str: A plain-English label for the sensor operating mode.

        Example:
            >>> SensorStatus.WARMING_UP.description
            'Warming Up'
        """
        _descriptions: dict[int, str] = {
            -2: "Chemical Sensor Off",
            -1: "Warming Up",
            0: "Zero",
            1: "Sample Acquisition",
            4: "Standart Gas Measurement for CO2 and SO2",
            6: "Standart Gas Measurement for H2S",
            10: "Manual Zero Measurement",
            11: "Manual Sample Measurement",
            14: "Manual Standart Gas Measurement for CO2 and SO2",
            16: "Manual Standart Gas Measurement for H2S",
        }
        return _descriptions[self.value]


class FileFormat(StrEnum):
    """Output file formats supported by writers in the multigas package.

    Values match the tokens accepted by the writer entry points and by
    downstream tooling that inspects the target format.

    Example:
        >>> FileFormat.CSV
        <FileFormat.CSV: 'csv'>
        >>> FileFormat("parquet").value
        'parquet'
    """

    CSV = "csv"
    EXCEL = "excel"
    PARQUET = "parquet"
    JSON = "json"


class ExtractedStats(TypedDict):
    """Per-day summary emitted by :meth:`MultiGasData.extract_daily`.

    One entry per calendar day in the source range that has data —
    days with no rows in the source frame are omitted from the
    results (and only reported in a ``WARNING`` log). The
    ``completeness`` value is a percentage in ``[0, 100]`` — it comes
    from :func:`multigas.utils.dataframe.calculate_completeness` with
    ``as_percentage=True`` (which also caps the value at ``100.0``
    and logs a ``WARNING`` when the raw ratio exceeds ``1.0``).

    Attributes:
        date: Calendar day, formatted as ``"YYYY-MM-DD"``.
        total_data: Number of rows written to the day's CSV.
        completeness: Percentage in ``[0, 100]`` from
            :func:`calculate_completeness` with ``as_percentage=True``.

    Example:
        >>> stats: ExtractedStats = {
        ...     "date": "2025-01-15",
        ...     "total_data": 1440,
        ...     "completeness": 100.0,
        ... }
        >>> stats["completeness"]
        100.0
    """

    date: str
    total_data: int
    completeness: float
