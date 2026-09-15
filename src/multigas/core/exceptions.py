"""Exception hierarchy for the multigas package.

All exceptions derive from :class:`MultigasException` so callers can catch the
entire family with a single ``except MultigasException`` clause. Dataset-level
failures share a common :class:`DatasetError` ancestor, letting callers narrow
handling to filter / column / date-range problems without listing each type.

Every exception in this module auto-logs its message on construction via the
shared :mod:`multigas.logging` logger. The recorded frame points at the
``raise`` site, not this file, so log lines remain useful, and when an
exception is being handled at raise-time (i.e. ``raise ... from e``) the log
includes the full traceback with the ``__cause__`` chain. When
``ENABLE_LOG`` is unset the logger has no handlers and the auto-log is a
no-op.

The default log level is ``ERROR``. A subclass can override the class-level
``_log_level`` attribute to log at a different loguru level — useful for
soft-failure exceptions where ``WARNING`` is more honest than ``ERROR``.
"""

import sys

from multigas.logging import logger


class MultigasException(Exception):
    """Base class for every exception raised by the multigas package.

    Catch this to intercept any package-specific failure without swallowing
    unrelated built-in exceptions. On construction the message is
    automatically logged through :mod:`multigas.logging` at the level named
    by the class-level :attr:`_log_level` attribute (``"ERROR"`` by
    default); every subclass inherits this behaviour and may override the
    level.

    Attributes:
        _log_level (str): Loguru level name used for the auto-log —
            ``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``, or
            ``"CRITICAL"``. Defaults to ``"ERROR"``. Override at the
            subclass level to change severity without touching call sites.

    Example:
        >>> try:
        ...     raise LoaderError("bad file")
        ... except MultigasException as exc:
        ...     print(type(exc).__name__)
        LoaderError
    """

    _log_level: str = "ERROR"

    def __init__(self, *args: object) -> None:
        """Initialise the exception and emit an auto-log line.

        Delegates to :class:`Exception` for the standard ``args`` handling,
        then logs the formatted message at :attr:`_log_level` via
        :mod:`multigas.logging`. ``logger.opt(depth=1, exception=True)``
        shifts the recorded frame one level up the stack so the log's
        ``{name}:{function}:{line}`` slot points at the ``raise`` site
        rather than this ``__init__``, and attaches the current exception's
        traceback (including the ``__cause__`` chain from
        ``raise ... from e``) when one is being handled. When no exception
        is active the ``exception=True`` flag is a no-op.

        Args:
            *args (object): Positional arguments forwarded to
                :class:`Exception`. The first argument, if any, becomes the
                exception message.

        Returns:
            None
        """
        super().__init__(*args)
        # Only attach a traceback when an exception is genuinely being
        # handled; otherwise loguru prints a bare "NoneType: None" tail.
        attach_traceback = sys.exc_info()[0] is not None
        logger.opt(depth=1, exception=attach_traceback).log(
            self._log_level, f"{type(self).__name__}: {self}"
        )


class DatasetError(MultigasException):
    """Raised for dataset-level operations that cannot complete.

    Parent of :class:`FilterError`, :class:`ColumnError`, and
    :class:`DateRangeError` — catch this to handle any dataset manipulation
    failure regardless of subclass.

    Example:
        >>> raise DatasetError("dataset is empty")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.DatasetError: dataset is empty
    """

    pass


class ValidationError(MultigasException):
    """Raised when input data fails a validation check.

    Example:
        >>> raise ValidationError("index is not monotonic")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.ValidationError: index is not monotonic
    """

    pass


class CacheError(MultigasException):
    """Raised when reading from or writing to the on-disk cache fails.

    Typically wraps a lower-level joblib or filesystem error.

    Example:
        >>> raise CacheError("cache file is corrupted")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.CacheError: cache file is corrupted
    """

    pass


class LoaderError(MultigasException):
    """Raised when a source file cannot be located, parsed, or normalised.

    Example:
        >>> raise LoaderError("File not found: data/site_a.dat")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.LoaderError: File not found: data/site_a.dat
    """

    pass


class MetadataError(MultigasException):
    """Raised when TOA5 (or equivalent) metadata cannot be extracted.

    Example:
        >>> raise MetadataError("missing station name in header")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.MetadataError: missing station name in header
    """

    pass


class FilterError(DatasetError):
    """Raised when a filter expression is invalid or produces no rows.

    Example:
        >>> raise FilterError("unknown comparator '~='")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.FilterError: unknown comparator '~='
    """

    pass


class ColumnError(DatasetError):
    """Raised for column-level failures — missing, duplicated, or wrong dtype.

    Example:
        >>> raise ColumnError("column 'CO2' is missing")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.ColumnError: column 'CO2' is missing
    """

    pass


class DateRangeError(DatasetError):
    """Raised when a requested date range cannot be applied to the dataset.

    Example:
        >>> raise DateRangeError("start date is after end date")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.DateRangeError: start date is after end date
    """

    pass


class PlotError(MultigasException):
    """Raised when a plotting routine cannot render its output.

    Example:
        >>> raise PlotError("no numeric columns to plot")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.PlotError: no numeric columns to plot
    """

    pass


class ConfigError(MultigasException):
    """Raised when the package configuration is missing or invalid.

    Example:
        >>> raise ConfigError("cache_dir must be an absolute path")
        Traceback (most recent call last):
            ...
        multigas.core.exceptions.ConfigError: cache_dir must be an absolute path
    """

    pass
