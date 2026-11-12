"""Plotting APIs, imported on demand to keep optional renderers lazy."""

from typing import Any
from pathlib import Path


__all__ = ["Plot", "plot_completeness"]


def __getattr__(name: str) -> Any:
    """Import plot APIs only when explicitly requested."""
    if name == "Plot":
        from multigas.plot.plot import Plot

        return Plot
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def plot_completeness(
    filepath: Path | str,
    title: str | None = None,
    verbose: bool = False,
) -> Path | None:
    """Render a daily-completeness CSV without importing plotting backends early.

    Args:
        filepath: Path to a completeness CSV.
        title: Optional chart title.
        verbose: Emit an informational message after saving.

    Returns:
        Path | None: Saved PNG path or ``None`` after a soft rendering failure.

    Example:
        >>> plot_completeness("output/daily/site-completeness.csv")
    """
    from multigas.plot.plot_completeness import plot_completeness as render

    return render(filepath, title=title, verbose=verbose)
