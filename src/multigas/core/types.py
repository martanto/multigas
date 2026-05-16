"""Shared type aliases, enums, and dataclasses for the multigas package."""

from enum import IntEnum, StrEnum, EnumMeta
from typing import TypedDict
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

import pandas as pd

from multigas.core.query import Query


DateLike = str | datetime | pd.Timestamp
ColumnName = str
Comparator = str


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
    """Types of datasets."""

    ONE_SECOND = "one_second"
    TWO_SECONDS = "two_seconds"
    SIX_HOURS = "six_hours"
    ONE_MINUTE = "one_minute"
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


@dataclass
class MultiGasData(Query):
    """A loaded DataFrame together with its provenance metadata and query capabilities.

    Extends Query to expose fluent column-selection and filtering methods directly
    on the loaded dataset.

    Attributes:
        df: The loaded (and optionally normalized) DataFrame.
        dataset_type: The type of dataset as declared by the caller.
        source_path: Absolute path to the original source file.
        index_col: Column name used as the datetime index.
        verbose: Whether to emit log messages for each operation.

    Example:
        >>> result = loader.load(path, DatasetType.ONE_MINUTE)
        >>> result.select_numeric_columns().df.head()
        >>> result.dataset_type
        <DatasetType.ONE_MINUTE: 'one_minute'>
    """

    df: pd.DataFrame
    dataset_type: DatasetType
    source_path: Path
    index_col: str = "TIMESTAMP"
    verbose: bool = False

    def __post_init__(self):
        """Initialise Query with the loaded DataFrame.

        Example:
            >>> result = MultiGasData(df, DatasetType.ONE_MINUTE, path)
            >>> result.numeric_columns  # populated by Query.__init__
        """
        Query.__init__(self, self.df, self.index_col, self.verbose)

    def __repr__(self) -> str:
        """Return a concise string representation of the dataset.

        Returns:
            str: A string showing dataset_type, source_path, and DataFrame shape.

        Example:
            >>> repr(result)
            "MultiGasData(dataset_type=<DatasetType.ONE_MINUTE: 'one_minute'>, ..., index_col='TIMESTAMP', drop_empty_columns=False, verbose=False)"
        """
        return (
            f"MultiGasData("
            f"dataset_type={self.dataset_type!r}, "
            f"source_path={self.source_path!r}, "
            f"shape={self.df.shape}, "
            f"index_col={self.index_col!r}, "
            f"verbose={self.verbose!r})"
        )


class DatasetMetadataDict(TypedDict, total=False):
    """Metadata extracted from dataset files."""

    station: str
    logger_type: str
    firmware: str
    program_name: str
    file_sampling: str
    serial_number: str
    os_version: str


class LogLevel(StrEnum):
    """Logging verbosity levels."""

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
    """Supported output file formats."""

    CSV = "csv"
    EXCEL = "excel"
    PARQUET = "parquet"
    JSON = "json"
