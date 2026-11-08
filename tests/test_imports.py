"""Tests to detect circular imports across all multigas modules."""

import importlib
import pkgutil
import sys
import subprocess

import pytest

MULTIGAS_MODULES = [
    "multigas",
    "multigas.config",
    "multigas.core",
    "multigas.core.exceptions",
    "multigas.core.types",
    "multigas.data",
    "multigas.data.loader",
    "multigas.data.multigas_data",
    "multigas.logging",
    "multigas.utils.analysis",
    "multigas.utils.daily",
    "multigas.plot.plot_timeseries",
    "multigas.api",
]


@pytest.mark.parametrize("module_name", MULTIGAS_MODULES)
def test_no_circular_import(module_name: str) -> None:
    """Each module can be imported in isolation without circular import errors.

    Args:
        module_name: Fully qualified module name to import.

    Raises:
        ImportError: If a circular import or other import error is detected.

    Returns:
        None

    Example:
        >>> # Run via pytest
        >>> # uv run pytest tests/test_imports.py -v
    """
    # Real process isolation also avoids invalidating exception/enum identities
    # and queued loguru records used by other tests in this interpreter.
    result = subprocess.run(
        [sys.executable, "-c", f"import importlib; importlib.import_module({module_name!r})"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
