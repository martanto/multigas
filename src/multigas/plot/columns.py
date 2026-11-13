"""Render observation-only time-series panels for numeric columns.

Example:
    >>> plot_columns("site.csv", ["Avg_CO2_lowpass", "Avg_SO2"], "6h")
    WindowsPath('output/figures/site-columns.png')
"""

from html import escape
from math import ceil
from typing import TYPE_CHECKING, cast
from hashlib import sha256
from pathlib import Path
from textwrap import fill
from collections.abc import Sequence

import numpy as np
import pandas as pd
from pandas.api.types import is_complex_dtype, is_numeric_dtype

from multigas.core.io import read_file
from multigas.core.types import DatasetType
from multigas.plot.six_hours import (
    PANELS,
    PNG_DPI,
    GRID_COLOR,
    TEXT_COLOR,
    MUTED_COLOR,
    EMPTY_MESSAGE,
)
from multigas.core.exceptions import PlotError, ColumnError, DatasetError
from multigas.plot.dimensions import validate_dimension
from multigas.utils.validation import check_columns_exist
from multigas.data.multigas_data import MultiGasData


if TYPE_CHECKING:
    from matplotlib.axes import Axes


def parse_column_names(column_names: str | Sequence[str]) -> list[str]:
    """Split comma-separated names, trim whitespace and deduplicate in order.

    Args:
        column_names (str | Sequence[str]): One comma-separated string or a
            sequence of strings.

    Returns:
        list[str]: Non-empty, distinct column names in input order.

    Raises:
        ValueError: If there are no names or any comma-separated name is empty.

    Example:
        >>> parse_column_names(["CO2, SO2", "CO2"])
        ['CO2', 'SO2']
    """
    tokens = [column_names] if isinstance(column_names, str) else column_names
    names = [name.strip() for token in tokens for name in token.split(",")]

    if not names or any(not name for name in names):
        raise ValueError(
            "Provide one or more non-empty column names; remove empty names."
        )

    return list(dict.fromkeys(names))


def _select_dates(
    frame: pd.DataFrame,
    start_date: str | pd.Timestamp | None,
    end_date: str | pd.Timestamp | None,
) -> pd.DataFrame:
    """Apply inclusive bounds and expand a date-only end to its full day.

    Args:
        frame (pd.DataFrame): Time-indexed observations to filter.
        start_date (str | pd.Timestamp | None): Inclusive lower date bound.
        end_date (str | pd.Timestamp | None): Inclusive upper date bound.

    Returns:
        pd.DataFrame: Chronologically sorted rows within the selected bounds.

    Raises:
        DatasetError: If the index or date range is invalid, or no rows match.
    """
    index = frame.index

    if not isinstance(index, pd.DatetimeIndex) or index.hasnans:
        raise DatasetError("Plot data must have a valid DatetimeIndex")

    try:
        start = pd.Timestamp(start_date) if start_date else None
        end = pd.Timestamp(end_date) if end_date else None

        if (start and pd.isna(start)) or (end and pd.isna(end)):
            raise ValueError("Date bounds must not be NaT")

        if isinstance(end_date, str) and len(end_date.strip()) == 10:
            end = pd.Timestamp(end_date) + pd.DateOffset(days=1) - pd.Timedelta(1, "ns")

        # Treat naive bounds as local dates for a timezone-aware input.
        timezone = index.tz

        if timezone:
            if start and start.tzinfo is None:
                start = start.tz_localize(timezone)
            if end and end.tzinfo is None:
                end = end.tz_localize(timezone)

        if start and end and start > end:
            raise ValueError("start_date must be on or before end_date")

        selected = frame.sort_index().loc[start:end]
    except (ValueError, TypeError, OverflowError) as exc:
        raise DatasetError(f"Invalid date range: {exc}") from exc

    if selected.empty:
        raise DatasetError(
            "No records in the selected date range; choose overlapping dates."
        )
    return selected


def _series_style(name: str) -> tuple[str, str]:
    """Return a chemical label and stable color for a column.

    Args:
        name (str): DataFrame column name.

    Returns:
        tuple[str, str]: Display label and hexadecimal color.
    """
    for panel in PANELS:
        if panel.column == name or (name == "H2O" and panel.column == "Avg_H2O"):
            return panel.html_label, panel.color

    for gas, color in (("SO2", "#B75226"), ("H2S", "#9C792C")):
        if name == f"Avg_{gas}_proportion":
            return f"{gas.replace('2', '₂')} proportion (%)", color

    slot = int.from_bytes(sha256(name.encode()).digest()[:4], "big") % len(PANELS)

    return name, PANELS[slot].color


def _caption(data: MultiGasData, frame: pd.DataFrame) -> str:
    """Describe the plotted window, exclusions, and gas caveats.

    Args:
        data (MultiGasData): Source dataset and provenance.
        frame (pd.DataFrame): Selected columns and date window.

    Returns:
        str: Single-paragraph figure caption.
    """
    invalid = int(frame.isna().sum().sum())

    text = (
        f"Source: {data.source_path}. Selected observations: {frame.index.min()} to "
        f"{frame.index.max()}. Observations only; linear axes show the full finite "
        "data range, without smoothing, clipping or outage shading. "
        f"Excluded {invalid} missing or nonfinite readings across selected columns. "
        "n counts finite readings. Units are not inferred from column names. "
    )

    gas_columns = [
        name
        for name in frame
        if any(g in str(name) for g in ("CO2", "SO2", "H2S", "H2O"))
    ]

    if gas_columns:
        text += (
            "Gas mixing-ratio units may be unspecified in the source TOA5 units row. "
        )

    if any(
        "H2S" in str(name) or "S_tot" in str(name) or "proportion" in str(name)
        for name in frame
    ):
        text += "H2S values are not corrected for SO2 cross-sensitivity. "

    if "Avg_SO2" in frame:
        so2: pd.Series = frame["Avg_SO2"]
        if so2.median() <= 0:
            text += "Median SO2 is at or below zero (sensor baseline); little real SO2 signal."

    return text.strip()


def plot_columns(
    source: str | Path | MultiGasData,
    column_names: str | Sequence[str],
    dataset_type: DatasetType | str | None = None,
    save_as: str = "PNG",
    output_dir: str | Path | None = None,
    verbose: bool = False,
    start_date: str | pd.Timestamp | None = None,
    end_date: str | pd.Timestamp | None = None,
    layout_columns: int = 2,
    width: float | None = None,
    height: float | None = None,
) -> Path:
    """Render one observation-only panel per selected numeric column.

    Args:
        source (str | Path | MultiGasData): CSV path or loaded dataset.
        column_names (str | Sequence[str]): Ordered names, optionally
            comma-separated; duplicates are removed.
        dataset_type (DatasetType | str | None, optional): Dataset type,
            required for paths and inferred for loaded data.
        save_as (str, optional): Output format: ``PNG``, ``PDF``, or ``HTML``.
            Defaults to ``"PNG"``.
        output_dir (str | Path | None, optional): Output root containing the
            ``figures`` directory. Defaults to ``./output``.
        verbose (bool, optional): Whether loading emits messages. Defaults to
            ``False``.
        start_date (str | pd.Timestamp | None, optional): Inclusive lower date
            bound.
        end_date (str | pd.Timestamp | None, optional): Inclusive upper date
            bound; date-only strings include the full day.
        layout_columns (int, optional): Number of panel columns, ``1`` or ``2``.
            Defaults to ``2``.
        width (float | None, optional): Whole-figure width in millimetres.
        height (float | None, optional): Whole-figure height in millimetres.

    Returns:
        Path: Saved <output-dir>/figures/<source-stem>-columns.<extension>.

    Raises:
        ValueError: Invalid dimensions, names, format, layout or path dataset type.
        ColumnError: Any requested columns are missing or nonnumeric.
        DatasetError: Conflicting type, invalid dates or no selected records.
        LoaderError: Source loading fails.
        PlotError: Export fails.

    Example:
        >>> path = plot_columns(
        ...     "site.csv", ["Avg_CO2_lowpass", "Avg_SO2"], "6h"
        ... )
        >>> path.name
        'site-columns.png'
    """
    width = validate_dimension(width, "width")
    height = validate_dimension(height, "height")
    names = parse_column_names(column_names)

    if isinstance(layout_columns, bool) or layout_columns not in (1, 2):
        raise ValueError("layout_columns must be 1 or 2")

    save_as = save_as.upper()

    if save_as not in {"PNG", "PDF", "HTML"}:
        raise ValueError("save_as must be PNG, PDF, or HTML")

    root = Path(output_dir) if output_dir else Path.cwd() / "output"

    if isinstance(source, MultiGasData):
        data = source
        if dataset_type and DatasetType(dataset_type) != data.dataset_type:
            raise DatasetError("Supplied dataset_type conflicts with MultiGasData type")
    else:
        if dataset_type is None:
            raise ValueError("dataset_type is required when source is a CSV path")
        data = read_file(
            source,
            dataset_type,
            normalize=True,
            drop_empty_columns=False,
            use_cache=False,
            output_dir=root,
            verbose=verbose,
        )

    check_columns_exist(names, data.df.columns.tolist())
    non_numerics: list[str] = []

    for name in names:
        series: pd.Series = data.df[name]
        if not bool(series.isna().all()) and (
            not is_numeric_dtype(series) or is_complex_dtype(series)
        ):
            non_numerics.append(name)

    if non_numerics:
        raise ColumnError(
            f"Non-numeric columns: {non_numerics}. Select real numeric columns or "
            "convert their readings to numbers before plotting."
        )

    frame = _select_dates(data.df, start_date, end_date)[names].copy()

    for name in names:
        values: pd.Series = pd.to_numeric(frame[name], errors="coerce")
        values = values.astype(float)
        frame[name] = values.where(np.isfinite(values))

    columns = min(layout_columns, len(names))
    path = root / "figures" / f"{data.basename}-columns.{save_as.lower()}"
    text = _caption(data, frame)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if save_as == "HTML":
            _render_html(frame, path, columns, text, width, height)
        else:
            _render_static(frame, path, columns, text, width, height)
    except Exception as exc:
        raise PlotError(f"Could not render {save_as} plot {path}: {exc}") from exc
    return path


def _render_static(
    frame: pd.DataFrame,
    path: Path,
    columns: int,
    text: str,
    width: float | None = None,
    height: float | None = None,
) -> None:
    """Render a static panel grid with a reserved caption band.

    Args:
        frame (pd.DataFrame): Finite observations to render by column.
        path (Path): Destination PNG or PDF path.
        columns (int): Number of panel columns.
        text (str): Figure caption.
        width (float | None, optional): Whole-figure width in millimetres.
        height (float | None, optional): Whole-figure height in millimetres.
    """
    import matplotlib

    matplotlib.use("Agg", force=True)
    import seaborn as sns
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.layout_engine import ConstrainedLayoutEngine

    from multigas.plot.dimensions import check_static_space, check_static_artists

    custom_size = width or height is not None
    width = (280 if width is None else width) / 25.4
    rows = ceil(len(frame.columns) / columns)
    wrapped = fill(
        text,
        width=max(1, int(205 * width / (280 / 25.4))),
        break_long_words=True,
        break_on_hyphens=False,
    )
    caption_inches = (wrapped.count("\n") + 1) * 6.2 * 1.25 / 72 + 0.15
    height = rows * 1.4 + 0.65 + caption_inches if height is None else height / 25.4

    if custom_size:
        check_static_space(width, height, rows, columns, caption_inches)
    bottom = caption_inches / height + (0.025 if custom_size else 0)

    with (
        plt.rc_context(
            {
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                "mathtext.fontset": "dejavusans",
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
                "text.color": TEXT_COLOR,
                "axes.titlecolor": TEXT_COLOR,
            }
        ),
        sns.axes_style("ticks"),
    ):
        fig, grid = plt.subplots(
            rows,
            columns,
            squeeze=False,
            sharex=True,
            figsize=(width, height),
            layout=ConstrainedLayoutEngine(
                hspace=0.18,
                wspace=0.06,
                rect=(0.015, bottom, 0.97, 0.93 - bottom),
            ),
        )

        try:
            axes = cast(list["Axes"], grid.ravel().tolist())
            dense = len(frame) > 1000
            for i, name in enumerate(frame.columns):
                ax = axes[i]
                label, color = _series_style(name)
                for panel in PANELS:
                    if panel.column == name or (
                        name == "H2O" and panel.column == "Avg_H2O"
                    ):
                        label = panel.label
                        break
                if name in {"Avg_SO2_proportion", "Avg_H2S_proportion"}:
                    gas = r"SO_2" if "SO2" in name else r"H_2S"
                    label = rf"$\mathbf{{{gas}}}$ proportion (%)"
                series: pd.Series = frame[name]
                values = series.dropna()
                known_label = label != name
                ax.set_title(
                    f"({i + 1})  {label}",
                    loc="left",
                    fontweight="bold",
                    parse_math=known_label,
                )
                ax.set_title(f"n = {len(values):,}", loc="right", fontsize=5.8)
                if values.empty:
                    ax.text(
                        0.5,
                        0.5,
                        EMPTY_MESSAGE,
                        transform=ax.transAxes,
                        ha="center",
                        va="center",
                        fontsize=6.3,
                        color=MUTED_COLOR,
                    )
                    ax.set_yticks([])
                else:
                    ax.scatter(
                        values.index,
                        values,
                        color=color,
                        linewidths=0,
                        s=3.5 if dense else 6,
                        alpha=0.4 if dense else 0.65,
                    )
                    if values.min() < 0 < values.max():
                        ax.axhline(0, color="#9A9A9A", linewidth=0.4)
                for side in ("top", "right"):
                    ax.spines[side].set_visible(False)
                ax.grid(True, color=GRID_COLOR, linewidth=0.3, linestyle=(0, (4, 3)))
                ax.set_axisbelow(True)
                ax.tick_params(which="major", length=2, pad=2)
                ax.tick_params(which="minor", length=1.2, width=0.4)
                lowest = i + columns >= len(frame.columns)
                ax.tick_params(axis="x", labelbottom=lowest)
                if lowest:
                    ax.set_xlabel("Date")
                locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
                ax.xaxis.set_major_locator(locator)
                ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
            for ax in axes[len(frame.columns) :]:
                ax.set_visible(False)
            start, end = frame.index.min(), frame.index.max()
            pad = max((end - start) * 0.015, pd.Timedelta(seconds=1))
            axes[0].set_xlim(start - pad, end + pad)
            fig.text(0.025, 0.98, path.stem, va="top", fontsize=8.5, fontweight="bold")
            fig.text(0.025, 0.025, wrapped, va="bottom", fontsize=6.2, linespacing=1.25)
            if custom_size:
                check_static_artists(fig)
            fig.savefig(path, dpi=PNG_DPI, facecolor="white")
        finally:
            plt.close(fig)


def _render_html(
    frame: pd.DataFrame,
    path: Path,
    columns: int,
    text: str,
    width: float | None = None,
    height: float | None = None,
) -> None:
    """Render linked datetime panels with hover values and a caption.

    Args:
        frame (pd.DataFrame): Finite observations to render by column.
        path (Path): Destination HTML path.
        columns (int): Number of panel columns.
        text (str): Figure caption.
        width (float | None, optional): Outer width in millimetres.
        height (float | None, optional): Outer height in millimetres.
    """
    from bokeh.embed import file_html
    from bokeh.models import Div, Title, Range1d, HoverTool
    from bokeh.layouts import column, gridplot
    from bokeh.plotting import figure
    from bokeh.resources import INLINE

    start, end = frame.index.min(), frame.index.max()
    pad = max((end - start) * 0.015, pd.Timedelta(seconds=1))
    shared = Range1d(start=start - pad, end=end + pad)
    plots = []

    for i, name in enumerate(frame.columns):
        label, color = _series_style(name)
        series: pd.Series = frame[name]
        values = series.dropna()
        plot = figure(
            width=1100 // columns,
            height=220,
            x_axis_type="datetime",
            x_range=shared,
            title=f"({i + 1}) {label}   n = {len(values):,}",
            tools="pan,wheel_zoom,box_zoom,reset,save",
        )
        points = plot.scatter(
            values.index.to_numpy(),
            values.to_numpy(),
            color=color,
            size=3.5 if len(frame) > 1000 else 4,
            alpha=0.4 if len(frame) > 1000 else 0.65,
            line_color=None,
        )
        plot.add_tools(
            HoverTool(
                renderers=[points],
                tooltips=[("Time", "@x{%F %T}"), ("Value", "@y")],
                formatters={"@x": "datetime"},
            )
        )
        if values.empty:
            plot.y_range = Range1d(start=0, end=1)
            plot.text(
                x=[start + (end - start) / 2],
                y=[0.5],
                text=[EMPTY_MESSAGE],
                text_align="center",
                text_color=MUTED_COLOR,
                text_font_size="11px",
            )
        plot.grid.grid_line_color = GRID_COLOR
        plot.grid.grid_line_dash = [4, 3]
        plot.outline_line_color = None
        plot.title = Title(
            text=f"({i + 1}) {label}   n = {len(values):,}", text_color=TEXT_COLOR
        )
        if i + columns >= len(frame.columns):
            plot.xaxis.axis_label = "Date"
        else:
            plot.xaxis.major_label_text_font_size = "0px"
        plots.append(plot)

    layout = column(
        Div(text=f"<h3>{escape(path.stem)}</h3>"),
        gridplot(plots, ncols=columns),
        Div(text=f"<p style='max-width:1100px'>{escape(text)}</p>"),
    )

    if width or height is not None:
        from multigas.plot.dimensions import size_html

        layout = size_html(plots, path.stem, text, columns, width, height, 1130, 220)

    path.write_text(file_html(layout, INLINE, path.stem), encoding="utf-8")
