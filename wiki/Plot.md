# Multi-GAS plotting

The plotting API renders six-hour (`6h`) multi-gas datasets as ten labeled
time-series panels in a two-column layout. It creates one figure for the
selected date range and a second figure for its trailing three months.

## Command line

```bash
uv run multigas plot data/site_a.csv --dataset-type 6h
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
wide and 190 mm high including its caption, which fits A4 landscape with
margins. That is wider than a Nature double column (183 mm); scale it to about
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
