"""Data loading and I/O utilities for multigas.

Exposes :class:`DataLoader`, the full-control loader that handles TOA5/CSV
parsing, DataFrame normalisation, and on-disk joblib caching, plus
:class:`MultiGasData`, the container that pairs a loaded DataFrame with its
provenance and the fluent :class:`~multigas.core.query.Query` interface. For a
one-call convenience wrapper see :func:`multigas.core.io.read_file`.

Example:
    >>> from multigas.data import DataLoader
    >>> loader = DataLoader(cache_dir="output/cache", verbose=True)
    >>> dataset = loader.load("data/site_a.dat", dataset_type="1min")
"""

from multigas.data.loader import DataLoader
from multigas.data.multigas_data import MultiGasData


__all__ = [
    "DataLoader",
    "MultiGasData",
]
