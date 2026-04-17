"""Tests to detect circular imports across all multigas modules."""

import importlib
import pkgutil
import sys

import pytest

MULTIGAS_MODULES = [
    "multigas",
    "multigas.config",
    "multigas.core",
    "multigas.core.exceptions",
    "multigas.core.types",
    "multigas.data",
    "multigas.data.loader",
    "multigas.logging",
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
    # Remove any previously cached imports to test isolation
    modules_to_remove = [m for m in sys.modules if m == module_name or m.startswith(f"{module_name}.")]
    for m in modules_to_remove:
        del sys.modules[m]

    importlib.import_module(module_name)
