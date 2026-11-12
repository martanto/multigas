# Multi-GAS plotting

For arbitrary numeric columns and any dataset type, use
[`plot columns`](#selected-column-figures). The standard six-hour API below
continues to produce its two fixed ten-panel figures.

The plotting API renders six-hour (`6h`) multi-gas datasets as ten labeled
time-series panels in a two-column layout by default. Set `columns=1` in
`Plot(...)` or pass `--one-column` on the CLI to stack panels (a) through (j)
in one column for PNG, PDF, or HTML. The Python `columns` argument accepts
only 1 or 2. It creates one figure for the selected date range and a second
figure for its trailing three months.

## Selected-column figures

```bash
uv run multigas plot columns Avg_CO2_lowpass Avg_SO2 \
  --source data/site_a.csv --dataset-type 6h \
  --start-date 2025-01-01 --end-date 2025-03-31
uv run multigas plot columns "Avg_CO2_lowpass, Avg_SO2" \
  --source data/site_a.csv --dataset-type 6h --save-as HTML --one-column --json
```

Names may be space-separated, comma-separated, or a quoted comma-separated
list. Whitespace is trimmed, duplicate names are removed in input order,
and empty names are errors. `--source` and `--dataset-type` are required;
all types (`1s`, `2s`, `6h`, `1min`, `zero`, `span`, `wx`) are supported.
Missing-column errors list every missing name and all available columns.
Nonnumeric selected columns are reported together; entirely missing columns
are retained and say "No valid readings in this period."

```python
from multigas.plot import plot_columns

figure = plot_columns(
    "data/site_a.csv", ["Avg_CO2_lowpass", "Avg_SO2"], dataset_type="6h",
    save_as="PDF", start_date="2025-01-01", end_date="2025-03-31",
    layout_columns=2,
)
```

Paths are loaded with normalization enabled and empty columns retained.
This API bypasses the cache so normalization and dataset-specific sampling
checks always run for the requested type. Sampling-interval modes remove
irregularly spaced records, including the first record after each gap.
An existing `MultiGasData` is used as supplied, without renormalizing or
mutating it; its type is inferred and a conflicting supplied type is rejected.

Optional date bounds are inclusive; either can be omitted. A date-only end
string includes the full calendar day. Invalid, reversed, or empty ranges
raise clear errors. Slicing happens before rendering and finite-value counts.

Each selected column gets a panel in input order. The default uses two
columns, while `--one-column` / `layout_columns=1` stacks them; a single
selection always uses one column. Figure height follows panel count. The
lowest occupied panel in each grid column carries date labels. Recognized
gas series retain their chemical labels and fixed palette colors; other
names are literal and receive stable colors from that palette.

These panels show observations against actual timestamps with linear axes
and full finite ranges. There are no trend lines, automatic logarithms,
robust clipping, or outage bands. Missing and infinite readings are excluded
and counted in the caption. The wrapped caption sits below the figure and
states source, observed dates, plotting conventions and relevant gas
caveats, without inventing units. Static figures follow the project font,
scatter and grid styling. PNG uses 300 dpi; PDF keeps editable vector text;
HTML embeds Bokeh resources and links time axes with timestamp/value hover.

One figure replaces `<output-dir>/figures/<source-stem>-columns.<extension>`;
the output root defaults to `./output`. The CLI prints a Rich summary, or
`{"figure": "..."}` with `--json`. `--verbose` enables loading logs.
Static figures are always closed, including when export fails.

## Command line

```bash
uv run multigas plot data/site_a.csv --dataset-type 6h
uv run multigas plot data/site_a.csv --dataset-type 6h --one-column
uv run multigas plot data/site_a.csv --dataset-type 6h --save-as PDF
uv run multigas plot data/site_a.csv --dataset-type 6h --save-as HTML
uv run multigas plot data/site_a.csv --dataset-type 6h \
  --start-date 2025-01-01 --end-date 2025-03-31 --json
```

The command supports PNG (default), vector PDF, and interactive HTML output.
Figures are written to `<output-dir>/figures`, which defaults to
`<cwd>/output/figures`.
The `--start-date` and `--end-date` bounds are inclusive and use
`YYYY-MM-DD`. If the selected range contains no records, the command exits
with an explicit error asking for a range that overlaps the dataset.

The Rich summary is shown by default. With `--json`, the command returns the
same two paths as `full_period` and `trailing_three_months` fields.

## Python API

`multigas.plot.Plot` accepts a CSV path or an existing `MultiGasData` object.
CSV paths require `dataset_type` and are loaded with normalization enabled;
the type is inferred from `MultiGasData`. A conflicting supplied type raises
`DatasetError`. The only supported layout is `DatasetType.SIX_HOURS`.

```python
from multigas.plot import Plot

plotter = Plot(
    "data/site_a.csv",
    dataset_type="6h",
    save_as="PNG",
    columns=1,  # Omit this argument for the default two-column layout.
    start_date="2025-01-01",
    end_date="2025-03-31",
)
paths = plotter.plot_all()
```

`plot_all()` returns a mapping with `full_period` and
`trailing_three_months` paths. Both date bounds are optional, and an end date
without a time includes the full calendar day. A range with no rows raises
`DatasetError` with an actionable message. Missing plot columns raise
`ColumnError` before rendering.

## Choosing a layout

| Layout | Python | CLI | Panel arrangement |
|---|---|---|---|
| Two columns (default) | `columns=2`, or omit | Omit `--one-column` | Five rows, read left to right, then top to bottom. |
| One column | `columns=1` | `--one-column` | Ten rows, panels (a) through (j) from top to bottom. |

The selection applies to both output periods and all three formats. PNG and
PDF keep the same width and double the figure height in one-column mode.
HTML stacks the same linked panels vertically. Date labels appear only on
the bottom row. Python raises `ValueError` for an invalid `columns` value.
Both layouts use the same output filenames; rendering again in the same
output directory replaces the previous figures.

## Panels and required columns

The ten panels show the following series, in order. Colors stay the same in
the full-period and trailing-three-month figures and come from the extended
Nature Reviews artwork palette. Panel letters `(a)` through `(j)`, black
titles with chemical subscripts, and marker shapes provide cues beyond color.

| Panel | Series | Color | Required columns |
|---:|---|---|---|
| a | CO2/S<sub>tot</sub> ratio | Olive `#738135` | `Avg_CO2_S_tot_ratio` |
| b | H2S/SO2 ratio | Green `#24743A` | `Avg_H2S_SO2_ratio` |
| c | CO2/H2S ratio | Teal `#136878` | `Avg_CO2_H2S_ratio` |
| d | CO2/SO2 ratio | Blue `#0E4F90` | `Avg_CO2_SO2_ratio` |
| e | H2O/CO2 ratio | Purple `#7A2C75` | `Avg_H2O_CO2_ratio` |
| f | CO2 concentration | Red `#9D2823` | `Avg_CO2_lowpass` |
| g | SO2 concentration | Orange `#B75226` | `Avg_SO2` |
| h | H2S concentration | Yellow-olive `#9C792C` | `Avg_H2S` |
| i | H2O concentration | Brown `#75503E` | `Avg_H2O` |
| j | SO2 and H2S proportions (%) | SO2 orange circles, H2S yellow-olive squares (matching panels g and h) | `Avg_SO2_proportion`, `Avg_H2S_proportion` |

## Reading the panels

- **Points and trend line.** Semi-transparent points are the recorded
  sample-cycle values. The darker line is a 7-day centred rolling median of
  daily medians. It needs at least three days with data inside the window, so
  it breaks across data gaps instead of bridging them.
- **Ratio axes.** A ratio panel uses a logarithmic y-axis when its values are
  all positive and span a decade or more; otherwise it stays linear.
- **Robust y-limits.** An extreme is left off the axis only when it lies more
  than twice the 1st-99th percentile span beyond that span (for example
  0-valued CO2 fault readings). PNG and PDF draw such values as open triangles
  on the axis edge and count them beside `n` in the panel header. HTML keeps
  them in the data; pan or zoom to reach them.
- **Sample count.** `n` in each panel header is the number of valid readings
  in the plotted window. A panel with none shows "No valid readings in this
  period".
- **Zero line.** Linear panels containing negative values (sensor baseline
  drift in SO2 or H2S) get a thin grey zero reference line.
- **Proportions.** Panel (j) is fixed to 0-100 %.
- **Data gaps.** Light-grey vertical bands mark periods of more than two
  days without any record, so a logger outage reads differently from a
  period where records exist but no valid ratio was computed.
- **SO2 baseline warning.** When the median SO2 of the plotted window is at
  or below zero, the caption states that the SO2-based panels (b), (d) and
  (j) rest on little real SO2 signal.

## Output formats

Matplotlib renders PNG and PDF; Bokeh renders HTML. The PDF is vector artwork
with editable text, and the PNG is rendered at 300 dpi. The figure is 280 mm
wide and 190 mm high in the default two-column layout, including its
caption, which fits A4 landscape with margins. One-column output keeps the
280 mm width and increases the height to 380 mm. The default figure is wider
than a Nature double column (183 mm); scale it to about
65 % for journal use. All three formats draw faint,
dashed light-grey gridlines at the major ticks of both axes, behind the data.
In HTML every panel frame has the same size. The proportion legend sits at
the top right of panel (j), in headroom above 100 % that no data can reach;
in PNG and PDF it sits above the panel, beside the title.
The HTML figure links the time axis of all ten panels, offers pan, wheel-zoom,
box-zoom, and reset tools, and shows the timestamp and value on hover.

Every figure ends with a caption that states the date window, axis,
trend-line and gap conventions, and two standing caveats: gas mixing-ratio units are not
labeled because the sample TOA5 units row is blank, and H2S values are not
corrected for SO2 cross-sensitivity. These Nature-inspired choices do not
certify compliance with any particular journal or manuscript stage. Palette
choices follow the Nature Reviews [conceptual artwork guide](https://www.nature.com/documents/natrev-artworkguide.pdf)
and the official [Nature figure preparation specifications](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/).
