"""Type definitions and enums."""

from enum import StrEnum
from typing import TypedDict
from datetime import datetime

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
