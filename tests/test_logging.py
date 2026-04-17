"""Tests for multigas.config.logging."""

import logging
import os
import shutil
from datetime import date
from pathlib import Path

import pytest

from multigas.config.logging import get_logger, setup_logging
from multigas.core.types import LogLevel

# Test output (log files) lives next to this file, per project convention.
TESTS_DIR = Path(__file__).parent
LOGS_DIR = TESTS_DIR / "logs"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_logger() -> None:
    """Remove all handlers from the multigas logger between tests."""
    log = logging.getLogger("multigas")
    for handler in log.handlers[:]:
        handler.close()
    log.handlers.clear()


@pytest.fixture(autouse=True)
def reset_logger():
    """Ensure a clean logger state before and after every test."""
    _fresh_logger()
    yield
    _fresh_logger()


@pytest.fixture()
def logs_dir(monkeypatch):
    """Chdir to TESTS_DIR so the 'logs/' folder lands in tests/logs/.

    Closes all multigas file handlers before teardown so Windows releases
    the log file lock, then removes the logs/ directory.
    """
    monkeypatch.chdir(TESTS_DIR)
    yield LOGS_DIR
    # Close file handlers before deletion — required on Windows.
    log = logging.getLogger("multigas")
    for handler in log.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
    log.handlers.clear()
    if LOGS_DIR.exists():
        shutil.rmtree(LOGS_DIR)


# ---------------------------------------------------------------------------
# setup_logging — level mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "log_level, expected",
    [
        (LogLevel.DEBUG, logging.DEBUG),
        (LogLevel.INFO, logging.INFO),
        (LogLevel.WARN, logging.WARNING),
        (LogLevel.ERROR, logging.ERROR),
    ],
)
def test_setup_logging_level(log_level, expected):
    logger = setup_logging(log_level)
    assert logger.level == expected


# ---------------------------------------------------------------------------
# setup_logging — console handler
# ---------------------------------------------------------------------------


def test_setup_logging_returns_logger():
    logger = setup_logging()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "multigas"


def test_setup_logging_has_console_handler():
    logger = setup_logging()
    stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)
                       and not isinstance(h, logging.FileHandler)]
    assert len(stream_handlers) == 1


def test_setup_logging_replaces_existing_handlers():
    setup_logging()
    setup_logging()  # second call must not accumulate handlers
    logger = logging.getLogger("multigas")
    assert len(logger.handlers) == 1


def test_console_handler_formatter():
    logger = setup_logging()
    handler = next(h for h in logger.handlers if isinstance(h, logging.StreamHandler)
                   and not isinstance(h, logging.FileHandler))
    fmt = handler.formatter._fmt  # type: ignore[union-attr]
    assert "%(asctime)s" in fmt
    assert "%(levelname)s" in fmt
    assert "%(message)s" in fmt


# ---------------------------------------------------------------------------
# setup_logging — file logging via explicit parameter
# ---------------------------------------------------------------------------


def test_file_logging_explicit_true(logs_dir):
    logger = setup_logging(enable_file_log=True)
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1


def test_file_logging_explicit_false(logs_dir):
    logger = setup_logging(enable_file_log=False)
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 0


def test_file_logging_creates_logs_directory(logs_dir):
    setup_logging(enable_file_log=True)
    assert logs_dir.is_dir()


def test_file_logging_creates_log_file(logs_dir):
    logger = setup_logging(enable_file_log=True)
    logger.info("test entry")
    expected_name = date.today().strftime("%Y-%m-%d") + ".log"
    log_file = logs_dir / expected_name
    assert log_file.exists()
    assert "test entry" in log_file.read_text(encoding="utf-8")


def test_file_log_filename_format(logs_dir):
    setup_logging(enable_file_log=True)
    expected_name = date.today().strftime("%Y-%m-%d") + ".log"
    assert (logs_dir / expected_name).exists()


def test_file_handler_uses_same_level(logs_dir):
    logger = setup_logging(LogLevel.DEBUG, enable_file_log=True)
    file_handler = next(h for h in logger.handlers if isinstance(h, logging.FileHandler))
    assert file_handler.level == logging.DEBUG


# ---------------------------------------------------------------------------
# setup_logging — file logging via ENABLE_LOG env variable
# ---------------------------------------------------------------------------


def test_enable_log_env_true(logs_dir, monkeypatch):
    monkeypatch.setenv("ENABLE_LOG", "true")
    logger = setup_logging()
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1


def test_enable_log_env_false(logs_dir, monkeypatch):
    monkeypatch.setenv("ENABLE_LOG", "false")
    logger = setup_logging()
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 0


def test_enable_log_env_missing_defaults_to_false(logs_dir, monkeypatch):
    monkeypatch.delenv("ENABLE_LOG", raising=False)
    logger = setup_logging()
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 0


def test_explicit_parameter_overrides_env(logs_dir, monkeypatch):
    """enable_file_log=False must win even when ENABLE_LOG=true in env."""
    monkeypatch.setenv("ENABLE_LOG", "true")
    logger = setup_logging(enable_file_log=False)
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 0


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


def test_get_logger_default_name():
    logger = get_logger()
    assert logger.name == "multigas"


def test_get_logger_custom_name():
    logger = get_logger("multigas.reader")
    assert logger.name == "multigas.reader"


def test_get_logger_returns_same_instance():
    assert get_logger() is get_logger()
