"""Headless, independent scientific MultiGas time-series rendering."""

from pathlib import Path

import numpy as np
import pandas as pd

from multigas.utils.analysis import PANEL_MAP, prepare_panels
from multigas.core.exceptions import PlotError


def plot_timeseries(
    df: pd.DataFrame,
    destination: Path | str,
    *,
    preset: str = "multigas-summary",
    panels: list[str] | None = None,
    units: dict[str, str] | None = None,
    ratio_source: str = "onboard",
    format: str | None = None,
    width: float = 10,
    height: float = 16,
    dpi: int = 300,
    start: str | None = None,
    end: str | None = None,
    y_limits: dict[str, tuple[float, float]] | None = None,
) -> Path:
    """Write aligned scatter panels to PNG, PDF, or SVG with scoped styling.

    Args:
        df (pd.DataFrame): Observations indexed by datetime.
        destination (Path | str): Explicit output path.
        preset (str): ``multigas-summary``.
        panels (list[str] | None): Ordered panel subset; all ten by default.
        units (dict | None): Confirmed source units.
        ratio_source (str): ``onboard`` or ``calculated``.
        format (str | None): Output format, or infer from destination suffix.
        width (float): Figure width in inches.
        height (float): Figure height in inches.
        dpi (int): Raster resolution.
        start (str | None): Inclusive lower UTC timestamp.
        end (str | None): Inclusive upper UTC timestamp.
        y_limits (dict | None): Explicit per-panel limits.

    Returns:
        Path: Written output path.

    Raises:
        PlotError: If inputs or output fail, including no usable observations.

    Example:
        >>> plot_timeseries(df, "summary.png", units={"Avg_SO2": "ppm"})
    """
    # No pyplot: FigureCanvasAgg is headless without changing the global backend.
    from matplotlib import dates, rc_context
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    figure = None
    try:
        path = Path(destination)
        output_format = (format or path.suffix.lstrip(".")).lower()
        if output_format not in {"png", "pdf", "svg"}:
            raise ValueError("Choose PNG, PDF, or SVG")
        if preset != "multigas-summary" or not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Use the multigas-summary preset and a DatetimeIndex")
        selected = list(PANEL_MAP) if panels is None else panels
        if not selected or any(p not in PANEL_MAP for p in selected):
            raise ValueError("Select at least one known panel")
        if not (1 <= width <= 30 and 1 <= height <= 40 and 50 <= dpi <= 600):
            raise ValueError("Invalid figure dimensions or DPI")
        frame = df.copy()
        index = pd.DatetimeIndex(frame.index)
        frame.index = (
            index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
        )
        frame = frame.sort_index()
        if start:
            frame = frame.loc[
                pd.Timestamp(start).tz_localize("UTC")
                if pd.Timestamp(start).tz is None
                else pd.Timestamp(start) :
            ]
        if end:
            upper = pd.Timestamp(end)
            frame = frame.loc[: upper.tz_localize("UTC") if upper.tz is None else upper]
        frame, provenance = prepare_panels(frame, units, ratio_source, selected)
        usable = [
            c
            for p in selected
            for c in PANEL_MAP[p].columns
            if c in frame and frame[c].notna().any()
        ]
        if not usable:
            raise ValueError("None of the selected panels has usable observations")
        with rc_context(
            {
                "font.family": "DejaVu Sans",
                "font.size": 9,
                "axes.facecolor": "white",
                "figure.facecolor": "white",
                "axes.spines.top": False,
                "axes.spines.right": False,
            }
        ):
            figure = Figure(figsize=(width, height), dpi=dpi)
            FigureCanvasAgg(figure)
            axes = figure.subplots(len(selected), 1, sharex=True, squeeze=False)[:, 0]
            for axis, panel_id in zip(axes, selected, strict=True):
                panel = PANEL_MAP[panel_id]
                available = False
                for column, color in zip(panel.columns, panel.colors, strict=True):
                    if column not in frame or not frame[column].notna().any():
                        continue
                    available = True
                    series = frame[column].dropna()
                    axis.scatter(
                        dates.date2num(series.index.to_numpy(dtype="datetime64[us]")),
                        series.to_numpy(),
                        s=3,
                        alpha=0.5,
                        color=color,
                        linewidths=0,
                        rasterized=True,
                        label=column.replace("Avg_", "").replace("_proportion", ""),
                    )
                unit = (
                    "%"
                    if panel_id == "proportions"
                    else (provenance.get(panel.columns[0], {}).get("unit", panel.unit))
                )
                axis.set_ylabel(
                    f"{panel.label}\n{unit}", fontweight="bold", labelpad=12
                )
                axis.grid(axis="y", color="#dddddd", linewidth=0.4)
                axis.tick_params(labelsize=8)
                if not available:
                    axis.text(
                        0.5,
                        0.5,
                        "column unavailable",
                        transform=axis.transAxes,
                        ha="center",
                        color="#666666",
                    )
                if panel_id == "proportions" and available:
                    axis.legend(loc="upper right", frameon=False, markerscale=3)
                if y_limits and panel_id in y_limits:
                    low, high = y_limits[panel_id]
                    if not np.isfinite([low, high]).all() or low >= high:
                        raise ValueError(f"Invalid y-limits for {panel_id}")
                    axis.set_ylim(low, high)
            locator = dates.AutoDateLocator(minticks=3, maxticks=8)
            axes[-1].xaxis.set_major_locator(locator)
            axes[-1].xaxis.set_major_formatter(dates.ConciseDateFormatter(locator))
            axes[-1].set_xlabel("Time (UTC)")
            if len(frame) > 1:
                axes[-1].set_xlim(frame.index.min(), frame.index.max())
            figure.subplots_adjust(
                left=0.17, right=0.97, top=0.98, bottom=0.05, hspace=0.16
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            figure.savefig(path, format=output_format, dpi=dpi, facecolor="white")
        return path
    except Exception as exc:
        raise PlotError(f"Scientific figure export failed: {exc}") from exc
    finally:
        if figure is not None:
            figure.clear()
