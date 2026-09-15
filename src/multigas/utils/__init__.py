"""Utility helpers for the multigas package.

Grouped by concern:

- :mod:`multigas.utils.path` — filesystem helpers such as :func:`ensure_dir`.
- :mod:`multigas.utils.cache` — joblib cache key / path / save / clear helpers.
- :mod:`multigas.utils.validation` — column and sampling-rate validators.
- :mod:`multigas.utils.dataframe` — DataFrame shaping helpers built on
  :mod:`multigas.utils.validation`.

Nothing is re-exported here; import the specific helper you need directly
from its submodule.
"""
