"""Shared figure sizing; importing this module loads no plotting backend."""

from math import ceil, isfinite
from numbers import Real
from textwrap import fill


def validate_dimension(value: float | None, name: str) -> float | None:
    """Validate an optional whole-figure dimension in millimetres.

    Args:
        value: Requested size, or None to retain the renderer default.
        name: Parameter name used in errors.

    Returns:
        float | None: Validated size.

    Raises:
        ValueError: Size is not a finite, positive real number.

    Example:
        >>> validate_dimension(200, "width")
        200.0
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite, positive real number in mm")
    try:
        valid = isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite, positive real number in mm")
    return float(value)


def check_static_space(
    width: float, height: float, rows: int, columns: int, caption_inches: float
) -> None:
    """Reject canvases without room for axes, unchanged fonts and a caption.

    Args:
        width: Canvas width in inches.
        height: Canvas height in inches.
        rows: Panel rows.
        columns: Panel columns.
        caption_inches: Reserved caption height in inches.

    Returns:
        None: The canvas has sufficient minimum space.

    Raises:
        ValueError: The panel grid cannot fit the requested canvas.

    Example:
        >>> check_static_space(10, 8, 5, 2, 0.5)
    """
    if width / columns < 1.8 or height - caption_inches - 0.65 < rows * 0.65:
        raise ValueError("Requested figure dimensions are too small for the layout")


def check_static_artists(fig) -> None:
    """Check rendered text bounds and axes after constrained layout runs.

    Args:
        fig: Matplotlib figure on an Agg canvas.

    Returns:
        None: Figure text, panel labels and caption fit the canvas.

    Raises:
        ValueError: Text is clipped, panels collapse or a caption overlaps labels.

    Example:
        >>> check_static_artists(figure)
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    text_boxes = []
    for text in fig.texts:
        box = text.get_window_extent(renderer)
        text_boxes.append(box)
        if (
            box.x0 < bounds.x0
            or box.x1 > bounds.x1
            or box.y0 < bounds.y0
            or box.y1 > bounds.y1
        ):
            raise ValueError(
                "Requested figure dimensions cannot accommodate figure text"
            )
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        if ax.bbox.width < 50 or ax.bbox.height < 20:
            raise ValueError(
                "Requested figure dimensions cannot accommodate the panels"
            )
        box = ax.get_tightbbox(renderer)
        if box is not None and (
            box.x0 < bounds.x0
            or box.x1 > bounds.x1
            or box.y0 < bounds.y0
            or box.y1 > bounds.y1
            or any(box.overlaps(text_box) for text_box in text_boxes)
        ):
            raise ValueError(
                "Requested figure dimensions cannot accommodate panel labels"
            )


def size_html(
    plots,
    title: str,
    text: str,
    columns: int,
    width: float | None,
    height: float | None,
    default_width: int,
    default_panel_height: int,
):
    """Build a fixed Bokeh canvas with explicit space for text and toolbar.

    Args:
        plots: Bokeh figures in reading order; resized in place.
        title: Figure heading.
        text: Full caption, escaped before embedding.
        columns: Panel columns.
        width: Optional outer width in millimetres.
        height: Optional outer height in millimetres.
        default_width: Default outer width in CSS pixels.
        default_panel_height: Automatic panel height in CSS pixels.

    Returns:
        Column: Fixed-size Bokeh layout containing heading, grid and caption.

    Raises:
        ValueError: There is insufficient space for panels and figure text.

    Example:
        >>> layout = size_html(plots, "Site", caption, 2, 300, 260, 1302, 212)
    """
    from html import escape

    from bokeh.models import Div
    from bokeh.layouts import column, gridplot

    rows = ceil(len(plots) / columns)
    outer_width = round(width * 96 / 25.4) if width is not None else default_width
    # Conservative text measure; retain the renderer's existing browser font.
    chars = max(1, (outer_width - 24) // 9)
    wrapped = fill(text, chars, break_long_words=True, break_on_hyphens=False)
    caption_height = len(wrapped.splitlines()) * 20 + 24
    title_height = max(48, ceil(len(title) / max(1, (outer_width - 24) // 11)) * 20 + 8)
    toolbar_height = 36
    overhead = title_height + caption_height + toolbar_height + 12
    outer_height = (
        round(height * 96 / 25.4)
        if height is not None
        else overhead + rows * default_panel_height
    )
    panel_width = (outer_width - 12) // columns
    panel_height = (outer_height - overhead) // rows
    if panel_width < 220 or panel_height < 110:
        raise ValueError(
            "Requested figure dimensions are too small for the HTML layout"
        )
    for plot in plots:
        plot.frame_width = None
        plot.frame_height = None
        plot.width = panel_width
        plot.height = panel_height
    heading = Div(
        text=f"<h3 style='margin:4px 0'>{escape(title)}</h3>",
        width=outer_width,
        height=title_height,
        margin=0,
        styles={"overflow-wrap": "anywhere"},
    )
    caption = Div(
        text=f"<p style='margin:0'>{escape(text)}</p>",
        width=outer_width,
        height=caption_height,
        margin=0,
        styles={
            "line-height": "20px",
            "padding": "0 6px",
            "box-sizing": "border-box",
            "overflow-wrap": "anywhere",
        },
    )
    grid = gridplot(plots, ncols=columns, toolbar_location="above")
    # gridplot(width=..., height=...) resizes every child plot. Set the
    # container separately to retain the panel budget computed above.
    grid.width = outer_width
    grid.height = rows * panel_height + toolbar_height
    grid.sizing_mode = "fixed"
    grid.margin = 0
    return column(
        heading,
        grid,
        caption,
        width=outer_width,
        height=outer_height,
        spacing=0,
        sizing_mode="fixed",
    )
