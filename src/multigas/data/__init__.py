"""Data loading and I/O utilities for multigas.

Exposes :class:`DataLoader`, the full-control loader that handles TOA5/CSV
parsing, DataFrame normalisation, and on-disk joblib caching. For a one-call
convenience wrapper see :func:`multigas.core.io.read_file`.

Example:
    >>> from multigas.data import DataLoader
    >>> loader = DataLoader(cache_dir="output/cache", verbose=True)
    >>> dataset = loader.load("data/site_a.dat", dataset_type="1min")
"""

from multigas.data.loader import DataLoader


__all__ = [
    "DataLoader",
]
