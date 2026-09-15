"""Core types, exceptions, and query infrastructure for multigas."""

from multigas.core.types import (
    DateLike,
    LogLevel,
    ColumnName,
    Comparator,
    FileFormat,
    DatasetType,
    MultiGasData,
    DatasetMetadataDict,
)
from multigas.core.exceptions import (
    PlotError,
    CacheError,
    ColumnError,
    ConfigError,
    FilterError,
    LoaderError,
    DatasetError,
    MetadataError,
    DateRangeError,
    ValidationError,
    MultigasException,
)


__all__ = [
    # Types
    "DateLike",
    "LogLevel",
    "ColumnName",
    "Comparator",
    "FileFormat",
    "DatasetType",
    "DatasetMetadataDict",
    "MultiGasData",
    # Exceptions
    "PlotError",
    "CacheError",
    "ColumnError",
    "ConfigError",
    "FilterError",
    "LoaderError",
    "DatasetError",
    "MetadataError",
    "DateRangeError",
    "ValidationError",
    "MultigasException",
]
