# Scientific time-series scatter plots

`multigas.plot.plot_timeseries` is reusable without FastAPI. It plots **every
finite observation** as a scatter point. It does not resample, select extrema,
or join points with lines. Plotting imports remain lazy relative to `import multigas`.

```python
from multigas.plot import plot_timeseries

plot_timeseries(
    dataset.df, "output/summary.png",
    units={"CO2_lowpass": "ppmv", "SO2": "ppmv", "H2S": "ppmv", "H2O": "ppmv",
           "SO2/S_total_3min": "%", "H2S/S_total_3min": "%"},
)
```

The source must have a `pd.DatetimeIndex`. Naive times are interpreted as UTC.
Use `to_datetime_index(frame, timestamp_column, utc=True)` at ingestion boundaries.
The default export is a 10 × 16 inch portrait PNG at 300 DPI. `format` supports
`png`, `pdf`, and `svg`; filename suffix is used when omitted. `width`, `height`,
`dpi`, inclusive UTC `start`/`end`, ordered `panels`, and per-panel `y_limits`
are configurable. `preset` is `"multigas-summary"`.

## Panel order

| ID | Label | Preferred channel |
|---|---|---|
| `co2_stot` | CO₂/Sₜₒₜ | `Avg_CO2_S_tot_ratio` / `CO2/S_total_ratio_3min` |
| `h2s_so2` | H₂S/SO₂ | `Avg_H2S_SO2_ratio` / `H2S/SO2_ratio_3min` |
| `co2_h2s` | CO₂/H₂S | `Avg_CO2_H2S_ratio` / `CO2/H2S_ratio_3min` |
| `co2_so2` | CO₂/SO₂ | `Avg_CO2_SO2_ratio` / `CO2/SO2_ratio_3min` |
| `h2o_co2` | H₂O/CO₂ | `Avg_H2O_CO2_ratio` / `H2O/CO2_ratio_3min` |
| `co2` | CO₂ | `Avg_CO2_lowpass` / `CO2_lowpass` / `CO2` |
| `so2` | SO₂ | `Avg_SO2` / `SO2` |
| `h2s` | H₂S | `Avg_H2S` / `H2S` |
| `h2o` | H₂O | `H2O` |
| `proportions` | Sulfur proportions | `Avg_SO2_proportion`, `Avg_H2S_proportion` / `SO2/S_total_3min`, `H2S/S_total_3min` |

Aliases are resolved without renaming or deleting original columns. The
definitions, colors, unit factors, formulas, and provenance in
`multigas.utils.analysis` are shared with the dashboard. Onboard ratios are
preferred by default; no calculated replacement is silently substituted.

## Calculated alternatives and units

Set `ratio_source="calculated"` to calculate instantaneous concentration
ratios. These differ scientifically from onboard sliding-window regression
slopes and are labeled calculated in provenance. Concentration units must be
confirmed and compatible: ppm/ppmv, ppb, percent, or fraction. All operands are
converted to ppm before division, including H₂O/CO₂. Zero and negative
denominators yield missing results. Nonfinite observations are not drawn.

Derived sulfur proportions are `100 × SO₂/(SO₂ + H₂S)` and
`100 × H₂S/(SO₂ + H₂S)`. Onboard proportions are displayed as percentages
only when the source unit confirms `%`/`percent` or `fraction`. Fractions are
multiplied by 100 and that conversion is recorded. Unconfirmed scaling makes
the panel unavailable. The Tangkuban Sec2 TOA5 header declares `%` explicitly.
H₂S is uncorrected for SO₂ cross-sensitivity; H₂S ratios and sulfur proportions
inherit that limitation.

## Rendering and failure behavior

Panels share a UTC time axis and have independent automatic vertical scales
including all finite points. Explicit `y_limits={"co2": (0, 2000)}` are allowed
and recorded. Missing channels remain in the preset with a “column unavailable”
annotation unless the caller explicitly excludes their panels. A request with
no usable observations raises `PlotError`.

The renderer uses headless `FigureCanvasAgg`, scoped `rc_context` styling,
small translucent scatter markers, rasterized artists for manageable vector
files, and guaranteed figure cleanup. It does not change global style/backend
or execute the standalone legacy plotting script. Export failures are hard
`PlotError`s because the caller explicitly requested a figure; the existing
daily-completeness plot retains its separate warning/`None` soft-failure contract.

The application performs figure exports as background jobs, at full resolution.
Its manifest records `kind="scatter"`, `resolution="full"`,
`downsampling=false`, source count, UTC range, ratio provenance, units, dimensions,
DPI, panels, and limits. Full-resolution rendering uses memory proportional
to the number of plotted points. Large ranges can take substantial time.

`tests/summary-reference.png` is a deterministic structural regression fixture,
not measured monitoring data. Tests inspect panel order, shared limits, independent
scales, outlier retention, legend, unavailable annotations, manual limits, all
three formats, global-style preservation, cleanup, and all-point scatter counts.
