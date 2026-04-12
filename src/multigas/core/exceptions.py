"""Custom exceptions"""


class MultigasException(Exception):
    """Base exception for all multigas errors."""

    pass


class DatasetError(MultigasException):
    """Raised when there are issues with dataset operations."""

    pass


class ValidationError(MultigasException):
    """Raised when data validation fails."""

    pass


class CacheError(MultigasException):
    """Raised when cache operations fail."""

    pass


class LoaderError(MultigasException):
    """Raised when file loading fails."""

    pass


class MetadataError(MultigasException):
    """Raised when metadata extraction or validation fails."""

    pass


class FilterError(DatasetError):
    """Raised when filtering operations fail."""

    pass


class ColumnError(DatasetError):
    """Raised when column operations fail (missing, invalid, etc.)."""

    pass


class DateRangeError(DatasetError):
    """Raised when date range operations fail."""

    pass


class PlotError(MultigasException):
    """Raised when plotting operations fail."""

    pass


class ConfigError(MultigasException):
    """Raised when configuration is invalid."""

    pass
