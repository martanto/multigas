"""Logging configuration for magma-multigas."""

import os
import sys
import logging
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from multigas.core.types import LogLevel


load_dotenv()

_LOGS_DIR = Path("logs")


def setup_logging(
    level: LogLevel = LogLevel.INFO,
    enable_file_log: bool | None = None,
) -> logging.Logger:
    """Setup logging with specified level.

    Reads ENABLE_LOG from the environment (.env) to decide whether to write
    logs to disk. The ``enable_file_log`` parameter overrides the env variable
    when provided explicitly.

    Args:
        level: Logging level (DEBUG, INFO, WARN, ERROR).
        enable_file_log: When True, log records are also written to a rotating
            file inside the ``logs/`` directory. Overrides the ``ENABLE_LOG``
            environment variable. Defaults to None (use env variable).

    Returns:
        Configured logger instance.

    Raises:
        OSError: If the ``logs/`` directory cannot be created.

    Example:
        >>> logger = setup_logging(LogLevel.DEBUG, enable_file_log=True)
        >>> logger.debug("debug message")
    """
    logger = logging.getLogger("multigas")

    # Remove existing handlers
    logger.handlers.clear()

    # Map LogLevel to logging levels
    level_map = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARN: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
    }

    log_level = level_map.get(level, logging.INFO)
    logger.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Resolve whether file logging is enabled
    if enable_file_log is None:
        enable_file_log = os.getenv("ENABLE_LOG", "false").strip().lower() == "true"

    if enable_file_log:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_filename = date.today().strftime("%Y-%m-%d") + ".log"
        file_handler = logging.FileHandler(_LOGS_DIR / log_filename, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get logger instance.

    Args:
        name: Logger name (default: multigas).

    Returns:
        Logger instance.

    Example:
        >>> logger = get_logger("multigas.reader")
    """
    if name is None:
        name = "multigas"
    return logging.getLogger(name)
