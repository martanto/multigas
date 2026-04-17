"""Type definitions and enums."""

from enum import StrEnum
from typing import TypedDict
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

import pandas as pd


DateLike = str | datetime | pd.Timestamp
ColumnName = str
Comparator = str


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
        values = ", ".join(f"`{m.value}`" for m in cls)
        attrs = ", ".join(f"`{cls.__name__}.{m.name}`" for m in cls)
        raise ValueError(
            f"{value!r} is not a valid {cls.__name__}. Valid values: {values} or {attrs}"
        )


@dataclass
class LoadedDataset:
    """A loaded DataFrame together with its provenance metadata.

    Attributes:
        df: The loaded (and optionally normalized) DataFrame.
        dataset_type: The type of dataset as declared by the caller.
        source_path: Absolute path to the original source file.

    Example:
        >>> result = loader.load(path, DatasetType.ONE_MINUTE)
        >>> result.df.head()
        >>> result.dataset_type
        <DatasetType.ONE_MINUTE: 'one_minute'>
    """

    df: pd.DataFrame
    dataset_type: DatasetType
    source_path: Path

    def __repr__(self) -> str:
        """Return a concise string representation of the dataset.

        Returns:
            str: A string showing dataset_type, source_path, and DataFrame shape.

        Example:
            >>> repr(result)
            "LoadedDataset(dataset_type=<DatasetType.ONE_MINUTE: 'one_minute'>, ...)"
        """
        return (
            f"LoadedDataset("
            f"dataset_type={self.dataset_type!r}, "
            f"source_path={self.source_path!r}, "
            f"shape={self.df.shape})"
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


class FileFormat(StrEnum):
    """Supported output file formats."""

    CSV = "csv"
    EXCEL = "excel"
    PARQUET = "parquet"
    JSON = "json"
