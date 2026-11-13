"""Expose plotting APIs without eagerly importing optional renderers.

Example:
    >>> from multigas.plot import Plot, plot_columns
    >>> plotter = Plot("site_6h.csv", "6h")
"""

from typing import Any
from pathlib import Path


__all__ = ["Plot", "plot_columns", "plot_completeness"]


def __getattr__(name: str) -> Any:
    """Import a plotting API only when it is explicitly requested.

    Args:
        name (str): Module attribute to resolve.

    Returns:
        Any: Lazily imported plotting class or function.

    Raises:
        AttributeError: If ``name`` is not a lazily exposed plotting API.
    """
    if name == "Plot":
        from multigas.plot.plot import Plot

        return Plot
    if name == "plot_columns":
        from multigas.plot.columns import plot_columns

        return plot_columns
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def plot_completeness(
    filepath: Path | str,
    title: str | None = None,
    verbose: bool = False,
) -> Path | None:
    """Render a daily-completeness CSV without importing plotting backends early.

    Args:
        filepath (Path | str): Path to a completeness CSV.
        title (str | None, optional): Chart title. Defaults to the file stem.
        verbose (bool, optional): Whether to log the saved path. Defaults to
            ``False``.

    Returns:
        Path | None: Saved PNG path or ``None`` after a soft rendering failure.

    Example:
        >>> plot_completeness("output/daily/site-completeness.csv")
    """
    from multigas.plot.plot_completeness import plot_completeness as render

    return render(filepath, title=title, verbose=verbose)
