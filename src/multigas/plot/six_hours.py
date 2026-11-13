"""Six-hour multi-gas plot layout and renderers."""

from typing import NamedTuple, cast
from pathlib import Path
from textwrap import fill

import numpy as np
import pandas as pd

from multigas.core.exceptions import PlotError
from multigas.data.multigas_data import MultiGasData


class Panel(NamedTuple):
    """One single-series panel of the six-hour layout."""

    label: str  # Mathtext title used by the PNG / PDF renderer.
    html_label: str  # Unicode title used by the HTML renderer.
    column: str
    color: str
    is_ratio: bool


# Extended Nature Reviews artwork palette; one fixed color per panel.
PANELS = [
    Panel(
        r"$\mathbf{CO_2/S_{tot}}$",
        "CO₂/S total",
        "Avg_CO2_S_tot_ratio",
        "#738135",
        True,
    ),
    Panel(r"$\mathbf{H_2S/SO_2}$", "H₂S/SO₂", "Avg_H2S_SO2_ratio", "#24743A", True),
    Panel(r"$\mathbf{CO_2/H_2S}$", "CO₂/H₂S", "Avg_CO2_H2S_ratio", "#136878", True),
    Panel(r"$\mathbf{CO_2/SO_2}$", "CO₂/SO₂", "Avg_CO2_SO2_ratio", "#0E4F90", True),
    Panel(r"$\mathbf{H_2O/CO_2}$", "H₂O/CO₂", "Avg_H2O_CO2_ratio", "#7A2C75", True),
    Panel(r"$\mathbf{CO_2}$", "CO₂", "Avg_CO2_lowpass", "#9D2823", False),
    Panel(r"$\mathbf{SO_2}$", "SO₂", "Avg_SO2", "#B75226", False),
    Panel(r"$\mathbf{H_2S}$", "H₂S", "Avg_H2S", "#9C792C", False),
    Panel(r"$\mathbf{H_2O}$", "H₂O", "Avg_H2O", "#75503E", False),
]
# Panel (j): (column, mathtext label, Unicode label, color, mpl marker, bokeh marker).
# Orange and blue distinguish the two overlaid proportions.
PROPORTIONS = [
    ("Avg_SO2_proportion", r"$\mathrm{SO_2}$", "SO₂", "#B75226", "o", "circle"),
    ("Avg_H2S_proportion", r"$\mathrm{H_2S}$", "H₂S", "#0E4F90", "s", "square"),
]
PROPORTION_LIMITS = (-5.0, 105.0)
SERIES = [(panel.html_label, panel.column) for panel in PANELS]
REQUIRED_COLUMNS = [panel.column for panel in PANELS] + [
    column for column, *_ in PROPORTIONS
]

TREND_DAYS = 7
TREND_MIN_DAYS = 3
EMPTY_MESSAGE = "No valid readings in this period"
TEXT_COLOR = "#171717"
MUTED_COLOR = "#5A5A5A"
GRID_COLOR = "#D2D2D2"
GRID_DASH = (4, 3)
GAP_COLOR = "#000000"
GAP_ALPHA = 0.025  # Faint tint; gridlines stay visible on top of it.
GAP_DAYS = 2
FIGURE_SIZE_MM = (280, 190)  # Fits A4 landscape with margins.
PNG_DPI = 300


def trend(values: pd.Series) -> pd.Series | None:
    """Compute a gap-aware rolling median for one plotted series.

    Daily medians are smoothed with a centred ``TREND_DAYS`` rolling median
    that needs at least ``TREND_MIN_DAYS`` days with data, so the line breaks
    across data gaps instead of bridging them.

    Args:
        values: Non-null readings indexed by a ``DatetimeIndex``.

    Returns:
        pd.Series | None: Daily trend stamped at midday (NaN inside gaps), or
            ``None`` when too few days have data to draw a line.

    Example:
        >>> line = trend(frame["Avg_SO2"].dropna())
    """
    if values.empty:
        return None
    daily = values.resample("1D").median()
    rolled = daily.rolling(TREND_DAYS, center=True, min_periods=TREND_MIN_DAYS).median()
    if rolled.notna().sum() < 2:
        return None
    rolled.index = cast(pd.DatetimeIndex, rolled.index) + pd.Timedelta(hours=12)
    return rolled


def y_axis(
    values: pd.Series, is_ratio: bool, log_scale: bool = False
) -> tuple[bool, float, float]:
    """Choose a readable y-scale and robust limits for one series.

    Ratios that are strictly positive use a log axis only when requested.
    On either side, an extreme is excluded from the axis only when it
    lies more than twice the 1-99 percentile span beyond that span, so a
    handful of faulty readings cannot flatten the rest of the record.

    Args:
        values: Non-null, non-empty readings.
        is_ratio: Whether the series is a dimensionless gas ratio.
        log_scale: Request log axes for positive ratios; default is linear.

    Returns:
        tuple[bool, float, float]: ``(use_log, lower, upper)`` axis settings.

    Example:
        >>> use_log, lower, upper = y_axis(frame["Avg_CO2_lowpass"].dropna(), False)
    """
    use_log = log_scale and is_ratio and float(values.min()) > 0
    scaled = values.map(np.log10) if use_log else values
    low, high = float(scaled.min()), float(scaled.max())
    core_low, core_high = (float(q) for q in scaled.quantile([0.01, 0.99]))
    span = core_high - core_low
    if span > 0:
        if core_low - low > 2 * span:
            low = core_low
        if high - core_high > 2 * span:
            high = core_high
    pad = 0.07 * (high - low) or max(abs(high), 1.0) * 0.05
    low, high = low - pad, high + pad
    if use_log:
        return True, float(10**low), float(10**high)
    return False, low, high


def gaps(index: pd.Index) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Find periods longer than ``GAP_DAYS`` without any record.

    Args:
        index: Sorted record timestamps of the plotted window.

    Returns:
        list[tuple[pd.Timestamp, pd.Timestamp]]: ``(last record before, first
            record after)`` for every gap, in time order.

    Example:
        >>> spans = gaps(frame.index)
    """
    steps = index.to_series().diff()
    after = steps.index[steps > pd.Timedelta(days=GAP_DAYS)]
    return [(stamp - steps[stamp], stamp) for stamp in after]


def log_ticks(lower: float, upper: float) -> list[float]:
    """List readable major ticks for a log axis.

    Args:
        lower: Positive lower axis limit.
        upper: Upper axis limit.

    Returns:
        list[float]: Decade ticks, plus 2x and 5x ticks when the range covers
            less than two decades.

    Example:
        >>> log_ticks(3, 40)
        [5.0, 10.0, 20.0]
    """
    mantissas = (1, 2, 5) if upper / lower < 100 else (1,)
    exponents = range(int(np.floor(np.log10(lower))), int(np.ceil(np.log10(upper))) + 1)
    ticks = [float(m * 10.0**e) for e in exponents for m in mantissas]
    return [tick for tick in ticks if lower <= tick <= upper]


def caption(
    data: MultiGasData, frame: pd.DataFrame, off_scale_note: str,
    log_scale: bool = False,
) -> str:
    """Build the explanatory caption shared by every renderer.

    Args:
        data: Dataset being plotted.
        frame: Non-empty rows of the plotted window.
        off_scale_note: Renderer-specific sentence about off-axis values.
        log_scale: Whether log axes were requested for positive ratios.

    Returns:
        str: Single-paragraph caption text.

    Example:
        >>> text = caption(data, frame, "Open triangles mark clipped values.")
    """
    start, end = frame.index.min(), frame.index.max()
    gap_note = (
        f"Grey bands mark periods of more than {GAP_DAYS} days without records. "
        if gaps(frame.index)
        else ""
    )
    # A zero or negative SO2 baseline undermines every SO2-derived quantity.
    so2_note = (
        "Median SO2 in this window is at or below zero (sensor baseline), so "
        "the SO2-based panels (b), (d) and (j) rest on little real SO2 signal. "
        if frame["Avg_SO2"].median() <= 0
        else ""
    )
    scale_note = (
        "logarithmic axes where all readings are positive, otherwise linear"
        if log_scale else "linear axes"
    )
    return (
        f"Six-hour observations from {data.basename}, {start:%Y-%m-%d} to "
        f"{end:%Y-%m-%d}. Panels (a)-(e) show gas ratios (dimensionless), on "
        f"{scale_note}; (f)-(i) show "
        "molar mixing ratios (unit not specified in the source TOA5 units row); "
        "(j) shows SO2 and H2S proportions (%). Points are recorded sample-cycle "
        f"values; lines are {TREND_DAYS}-day centred rolling medians of daily "
        f"medians, broken across data gaps. n is the number of valid readings. "
        f"{off_scale_note} {gap_note}{so2_note}H2S values are not corrected for "
        "SO2 cross-sensitivity."
    )


def render(
    data: MultiGasData, start: pd.Timestamp, end: pd.Timestamp, path: Path, save_as: str,
    columns: int = 2,
    width: float | None = None,
    height: float | None = None,
    log_scale: bool = False,
) -> Path:
    """Render one date window using the requested backend.

    Args:
        data: Loaded dataset with the required six-hour plot columns.
        start: Inclusive start timestamp.
        end: Inclusive end timestamp.
        path: Destination file path.
        save_as: Renderer format, ``PNG``, ``PDF``, or ``HTML``.
        columns: Number of panel columns, 1 or 2.
        width: Optional whole-figure width in mm.
        height: Optional whole-figure height in mm.
        log_scale: Use log axes for positive ratios; default is linear.

    Raises:
        PlotError: If the window is empty or the renderer fails.

    Returns:
        Path: The saved figure path.

    Example:
        >>> render(data, data.df.index.min(), data.df.index.max(), path, "PNG")
    """
    frame = data.df.loc[start:end]
    if frame.empty:
        raise PlotError(f"No data available in plot period {start} to {end}")
    try:
        if save_as in {"PNG", "PDF"}:
            _render_static(
                data, frame, start, end, path, save_as, columns, width, height, log_scale
            )
        else:
            _render_html(data, frame, start, end, path, columns, width, height, log_scale)
    except Exception as exc:
        raise PlotError(f"Could not render {save_as} plot {path}: {exc}") from exc
    return path


def _minor_log_label(value: float, _position: float) -> str:
    """Label only the 2x and 5x minor ticks of a log axis."""
    if value <= 0:
        return ""
    digit = round(value / 10 ** np.floor(np.log10(value)))
    return f"{value:g}" if digit in {2, 5} else ""


def _render_static(
    data: MultiGasData,
    frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    path: Path,
    save_as: str,
    columns: int = 2,
    width: float | None = None,
    height: float | None = None,
    log_scale: bool = False,
) -> None:
    """Render the ten-panel figure to PNG or vector PDF with matplotlib."""
    import matplotlib

    matplotlib.use("Agg", force=True)
    import seaborn as sns
    import matplotlib.dates as mdates
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt
    import matplotlib.patheffects as patheffects
    from matplotlib.ticker import FuncFormatter, NullFormatter
    from matplotlib.layout_engine import ConstrainedLayoutEngine

    from multigas.plot.dimensions import check_static_space, check_static_artists

    custom_size = width is not None or height is not None
    width = (FIGURE_SIZE_MM[0] if width is None else width) / 25.4
    height = (FIGURE_SIZE_MM[1] * (2 if columns == 1 else 1)
              if height is None else height) / 25.4
    caption_size = 6.2
    spans = gaps(frame.index)
    text = fill(
        caption(
            data,
            frame,
            "Open triangles mark values beyond the displayed axis range.",
            log_scale=log_scale,
        ),
        width=max(1, int(width * 138 / caption_size)),
        break_on_hyphens=False,
    )
    caption_height = (text.count("\n") + 1) * caption_size * 1.25 / (height * 72)
    bottom = caption_height + 0.03
    if custom_size:
        check_static_space(width, height, 10 // columns, columns,
                           caption_height * height)
    # Rect is (left, bottom, width, height); the caption sits in the bottom band.
    engine = ConstrainedLayoutEngine(
        hspace=0.18, wspace=0.06, rect=(0.015, bottom, 0.95, 0.955 - bottom)
    )
    dense = len(frame) > 1000
    point_style = {
        "s": 3.5 if dense else 6,
        "alpha": 0.4 if dense else 0.65,
        "linewidths": 0,
    }

    def draw(
        axis,
        values: pd.Series,
        color: str,
        marker: str,
        lower: float,
        upper: float,
        label: str | None = None,
    ) -> list[str]:
        notes = []
        inside = values[(values >= lower) & (values <= upper)]
        axis.scatter(
            inside.index,
            inside,
            color=color,
            marker=marker,
            label=label,
            rasterized=False,
            **point_style,
        )
        for clipped, edge, symbol, side in (
            (values[values < lower], lower, "v", "below"),
            (values[values > upper], upper, "^", "above"),
        ):
            if clipped.empty:
                continue
            axis.scatter(
                clipped.index,
                np.full(len(clipped), edge),
                marker=symbol,
                s=9,
                facecolors="none",
                edgecolors=color,
                linewidths=0.5,
                clip_on=False,
                zorder=4,
            )
            notes.append(f"{len(clipped)} {side} axis")
        line = trend(values)
        if line is not None:
            # Darkened line with a white halo stays legible over dense points.
            dark = tuple(0.6 * channel for channel in mcolors.to_rgb(color))
            axis.plot(
                line.index,
                line,
                color=dark,
                linewidth=0.9,
                zorder=3,
                path_effects=[
                    patheffects.withStroke(linewidth=2.0, foreground="white")
                ],
            )
        return notes

    def finish(axis, title: str) -> None:
        axis.set_title(
            title, loc="left", pad=2, fontsize=7.6, fontweight="bold", color=TEXT_COLOR
        )
        axis.grid(
            True,
            which="major",
            color=GRID_COLOR,
            linewidth=0.3,
            linestyle=(0, GRID_DASH),
        )
        axis.set_axisbelow(True)
        for left, right in spans:
            axis.axvspan(
                left, right, color=GAP_COLOR, alpha=GAP_ALPHA, linewidth=0, zorder=0
            )
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(axis="both", which="major", length=2, pad=2)
        axis.tick_params(axis="both", which="minor", length=1.2, width=0.4)

    def mark_empty(axis) -> None:
        axis.set_yticks([])
        axis.text(
            0.5,
            0.5,
            EMPTY_MESSAGE,
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=6.3,
            color=MUTED_COLOR,
        )

    with (
        plt.rc_context(
            {
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                "mathtext.fontset": "custom",
                "mathtext.rm": "sans",
                "mathtext.bf": "sans:bold",
                "axes.labelsize": 6.6,
                "axes.titlesize": 7.6,
                "xtick.labelsize": 6.3,
                "ytick.labelsize": 6.3,
                "axes.linewidth": 0.55,
                "xtick.major.width": 0.55,
                "ytick.major.width": 0.55,
                "pdf.fonttype": 42,
                "ps.fonttype": 42,
                "savefig.bbox": None,
            }
        ),
        sns.axes_style("ticks"),
    ):
        figure, axes_grid = plt.subplots(
            10 // columns, columns, figsize=(width, height), sharex=True, layout=engine
        )
        try:
            axes = axes_grid.ravel()
            for index, (panel_axis, panel) in enumerate(
                zip(axes[:9], PANELS, strict=True)
            ):
                panel_values = frame[panel.column].dropna()
                if panel_values.empty:
                    mark_empty(panel_axis)
                else:
                    use_log, lower_limit, upper_limit = y_axis(
                        panel_values, panel.is_ratio, log_scale
                    )
                    if use_log:
                        panel_axis.set_yscale("log")
                        panel_axis.yaxis.set_major_formatter(
                            FuncFormatter(lambda value, _: f"{value:g}")
                        )
                        # Narrow log ranges get 2x and 5x labels so that
                        # more than one tick is readable.
                        panel_axis.yaxis.set_minor_formatter(
                            FuncFormatter(_minor_log_label)
                            if upper_limit / lower_limit < 100
                            else NullFormatter()
                        )
                    elif lower_limit < 0 < upper_limit and panel_values.min() < 0:
                        panel_axis.axhline(0, color="#9A9A9A", linewidth=0.4, zorder=0)
                    clipping_notes = draw(
                        panel_axis,
                        panel_values,
                        panel.color,
                        "o",
                        lower_limit,
                        upper_limit,
                    )
                    panel_axis.set_ylim(lower_limit, upper_limit)
                    panel_axis.set_title(
                        " · ".join([f"n = {len(panel_values):,}", *clipping_notes]),
                        loc="right",
                        pad=2,
                        fontsize=5.8,
                        color=MUTED_COLOR,
                    )
                finish(panel_axis, f"({chr(97 + index)})  {panel.label}")

            visible = 0
            for (
                column,
                proportion_label,
                _,
                proportion_color,
                proportion_marker,
                _,
            ) in PROPORTIONS:
                proportion_values = frame[column].dropna()
                if proportion_values.empty:
                    continue
                draw(
                    axes[9],
                    proportion_values,
                    proportion_color,
                    proportion_marker,
                    *PROPORTION_LIMITS,
                    proportion_label,
                )
                visible += 1
            if visible:
                axes[9].set_ylim(*PROPORTION_LIMITS)
                axes[9].set_yticks([0, 25, 50, 75, 100])
                axes[9].legend(
                    loc="lower right",
                    bbox_to_anchor=(1, 1.025),
                    borderaxespad=0,
                    frameon=False,
                    ncols=2,
                    fontsize=6.3,
                    handletextpad=0.3,
                    columnspacing=0.8,
                    markerscale=1.6,
                )
            else:
                mark_empty(axes[9])
            finish(
                axes[9],
                r"(j)  $\mathbf{SO_2}$ and $\mathbf{H_2S}$ proportions (%)",
            )

            pad = max((end - start) * 0.015, pd.Timedelta(hours=6))
            axes[9].set_xlim(start - pad, end + pad)
            for date_axis in axes[-columns:]:
                date_axis.set_xlabel("Date", labelpad=3, fontsize=6.6)
                locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
                date_axis.xaxis.set_major_locator(locator)
                date_axis.xaxis.set_major_formatter(
                    mdates.ConciseDateFormatter(locator)
                )
            figure.text(
                0.02,
                0.985,
                f"{data.basename} | {start:%Y-%m-%d} to {end:%Y-%m-%d}",
                ha="left",
                va="top",
                fontsize=8.5,
                fontweight="bold",
                color=TEXT_COLOR,
            )
            figure.text(
                0.02,
                bottom - 0.012,
                text,
                ha="left",
                va="top",
                fontsize=caption_size,
                color=TEXT_COLOR,
                linespacing=1.25,
            )
            if custom_size:
                check_static_artists(figure)
            figure.savefig(
                path,
                dpi=PNG_DPI if save_as == "PNG" else None,
                facecolor="white",
                format=save_as.lower(),
                bbox_inches=None,
            )
        finally:
            plt.close(figure)


def _render_html(
    data: MultiGasData,
    frame: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    path: Path,
    columns: int = 2,
    width: float | None = None,
    height: float | None = None,
    log_scale: bool = False,
) -> None:
    """Render the ten-panel figure to interactive HTML with Bokeh."""
    from bokeh.models import (
        Div,
        Range1d,
        HoverTool,
        UIElement,
        FixedTicker,
        BoxAnnotation,
    )
    from bokeh.layouts import column, gridplot
    from bokeh.plotting import save, figure, output_file

    pad = max((end - start) * 0.015, pd.Timedelta(hours=6))
    x_range = Range1d(start=start - pad, end=end + pad)
    spans = gaps(frame.index)
    hover = [("Time", "@x{%F %H:%M}"), ("Value", "@y{0.[0000]}")]

    def new_figure(title: str, use_log: bool, lower: float, upper: float):
        plot = figure(
            frame_width=560,
            frame_height=160,
            min_border_left=58,
            x_axis_type="datetime",
            x_range=x_range,
            y_axis_type="log" if use_log else "linear",
            y_range=Range1d(start=lower, end=upper),
            title=title,
            tools="pan,wheel_zoom,box_zoom,reset",
            min_border_right=18,
        )
        if use_log:
            ticks = log_ticks(lower, upper)
            plot.yaxis.ticker = FixedTicker(ticks=ticks)
            plot.yaxis.major_label_overrides = {tick: f"{tick:g}" for tick in ticks}
        plot.grid.grid_line_color = GRID_COLOR
        plot.grid.grid_line_dash = list(GRID_DASH)
        plot.outline_line_color = None
        for left, right in spans:
            plot.add_layout(
                BoxAnnotation(
                    left=left,
                    right=right,
                    fill_color=GAP_COLOR,
                    fill_alpha=GAP_ALPHA,
                    line_color=None,
                    level="image",
                )  # Below the grid's underlay level.
            )
        return plot

    def draw(
        plot, values: pd.Series, color: str, marker: str, label: str | None = None
    ) -> None:
        legend_options = {} if label is None else {"legend_label": label}
        points = plot.scatter(
            x=values.index.to_numpy(),
            y=values.to_numpy(),
            size=4,
            color=color,
            alpha=0.45,
            marker=marker,
            **legend_options,
        )
        plot.add_tools(
            HoverTool(renderers=[points], tooltips=hover, formatters={"@x": "datetime"})
        )
        line = trend(values)
        if line is not None:
            plot.line(
                x=line.index.to_numpy(), y=line.to_numpy(), color=color, line_width=1.6
            )

    plots: list[UIElement | None] = []
    for index, panel in enumerate(PANELS):
        panel_values = frame[panel.column].dropna()
        panel_title = f"({chr(97 + index)})  {panel.html_label}"
        if panel_values.empty:
            panel_plot = new_figure(panel_title, False, 0, 1)
            panel_plot.yaxis.visible = False
            panel_plot.text(
                x=[start + (end - start) / 2],
                y=[0.5],
                text=[EMPTY_MESSAGE],
                text_align="center",
                text_baseline="middle",
                text_font_size="11px",
                text_color=MUTED_COLOR,
            )
        else:
            panel_plot = new_figure(
                f"{panel_title}   (n = {len(panel_values):,})",
                *y_axis(panel_values, panel.is_ratio, log_scale),
            )
            draw(panel_plot, panel_values, panel.color, "circle")
        if index >= 10 - columns:
            panel_plot.xaxis.axis_label = "Date"
        else:
            # Only the bottom row carries date labels; ticks stay on every panel.
            panel_plot.xaxis.major_label_text_font_size = "0px"
            panel_plot.xaxis.major_label_standoff = 0
        plots.append(panel_plot)

    # Proportions cannot exceed 100 %, so headroom above 100 holds the legend
    # without overlapping data or changing the frame size.
    bottom = new_figure(
        "(j)  SO₂ and H₂S proportions (%)", False, PROPORTION_LIMITS[0], 132
    )
    bottom.yaxis.ticker = FixedTicker(ticks=[0, 25, 50, 75, 100])
    for (
        column_name,
        _,
        proportion_label,
        proportion_color,
        _,
        proportion_marker,
    ) in PROPORTIONS:
        proportion_values = frame[column_name].dropna()
        if not proportion_values.empty:
            draw(
                bottom,
                proportion_values,
                proportion_color,
                proportion_marker,
                proportion_label,
            )
    if bottom.legend:
        legend = bottom.legend[0]
        legend.orientation = "horizontal"
        legend.location = "top_right"
        legend.border_line_color = None
        legend.background_fill_alpha = 0
        legend.label_text_font_size = "11px"
        legend.padding = 2
        legend.margin = 2
    bottom.xaxis.axis_label = "Date"
    plots.append(bottom)

    period = f"{start:%Y-%m-%d} to {end:%Y-%m-%d}"
    output_file(path, title=f"{data.basename} ({period})")
    text = caption(
        data,
        frame,
        "Extreme values can lie outside the initial y-range; pan or zoom to "
        "reach them.",
        log_scale=log_scale,
    )
    if width is not None or height is not None:
        from multigas.plot.dimensions import size_html

        save(size_html(plots, f"{data.basename} | {period}", text, columns,
                       width, height, columns * 636 + 30, 212))
        return
    save(
        column(
            Div(text=f"<h3 style='margin:4px 0'>{data.basename} | {period}</h3>"),
            gridplot(plots, ncols=columns, toolbar_location="right"),
            Div(text=f"<p style='max-width:1240px'>{text}</p>"),
        )
    )
