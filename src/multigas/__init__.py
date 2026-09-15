#!/usr/bin/env python
"""multigas — Python package for processing multi-gas volcanic monitoring data.

Provides :class:`DataLoader` for reading, normalising, and caching CSV/Excel
files produced by Campbell Scientific dataloggers, and :func:`read_file` as a
convenient one-call entry point.

Example:
    >>> from multigas import read_file
    >>> ds = read_file("data/site_a.dat", dataset_type="1min")
    >>> ds.df.head()
"""

from importlib.metadata import version

from multigas.core.io import read_file
from multigas.data.loader import DataLoader


__version__ = version("multigas")
__author__ = "Martanto"
__author_email__ = "martanto@live.com"
__license__ = "MIT"
__copyright__ = "Copyright (c) 2026, Martanto"
__url__ = "https://github.com/martanto/multigas"

__all__ = [
    "__version__",
    "__author__",
    "__author_email__",
    "__license__",
    "__copyright__",
    "__url__",
    "read_file",
    "DataLoader",
]
