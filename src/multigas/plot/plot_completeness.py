"""Daily-completeness plotting for extracted multi-gas datasets.

Renders the per-day completeness summary written by
:meth:`multigas.data.MultiGasData.extract_daily` as a bar-style
availability chart via the ``data-availability`` package.

Example:
    >>> from multigas.plot import plot_completeness
    >>> plot_completeness("output/daily/one-minute/site-a-completeness.csv")
    PosixPath('output/daily/one-minute/site-a-completeness.png')
"""

from pathlib import Path

import matplotlib.pyplot as plt
from data_availability import PlotAvailability

from multigas.logging import logger


def plot_completeness(
    filepath: Path | str,
    title: str | None = None,
    verbose: bool = False,
) -> Path | None:
    """Plot a daily-completeness CSV and save it as a PNG next to the source.

    Reads a CSV with ``date`` (``YYYY-MM-DD``) and ``completeness``
    (percentage in ``[0, 100]``) columns, draws a bar-style availability
    chart, and writes it to the same path with a ``.png`` suffix. The
    figure is always closed after saving so repeated calls do not leak
    open matplotlib figures.

    Plotting is a secondary output, so failures are soft: any exception
    raised while reading, drawing, or saving is logged at ``WARNING``
    and ``None`` is returned instead of propagating.

    Args:
        filepath (Path | str): Path to the completeness CSV.
        title (str | None): Figure title. Defaults to the CSV file stem
            when ``None``.
        verbose (bool): Log the saved figure path at ``INFO``. Defaults
            to ``False``.

    Returns:
        Path | None: Path of the saved PNG, or ``None`` if plotting
            failed.

    Example:
        >>> plot_completeness("site-a-completeness.csv", title="site_a (one-minute)")
        PosixPath('site-a-completeness.png')
    """
    filepath = Path(filepath)
    figure_filepath = filepath.with_suffix(".png")

    try:
        fig = (
            PlotAvailability(filepath)
            .select()
            .plot(
                title=title or filepath.stem,
                kind="bar",
                hspace=2,
                fig_width=10,
                figsize_per_year=0.8,
                cbar_height=5,
            )
        )
        try:
            fig.savefig(figure_filepath, dpi=150, bbox_inches="tight")
        finally:
            plt.close(fig)
    except Exception as e:
        logger.warning(f"Could not plot completeness for {filepath}: {e}")
        return None

    if verbose:
        logger.info(f"Saved completeness figure to {figure_filepath}")

    return figure_filepath
