# Wind Analysis

Compass-sector and quadrant lookup for bearings recorded alongside the gas
data. `multigas` ships three sector tables (4-, 8-, and 16-way) plus two
quadrant tables (4- and 8-way), and two `MultiGasData` methods that use
them to attach a label column to the DataFrame.

> Back to [Home](Home.md) · Related: [API Reference → `MultiGasData`](API-Reference.md#multigasdata).

Modules: `multigas.core.constant`, `multigas.utils.dataframe`,
`multigas.core.types`.

---

## Quick Start

```python
from multigas import read_file

ds = read_file("data/site_a.dat", dataset_type="1min")

# 16-sector compass label (default), full names
ds.add_wind_direction("WD_deg")
ds.df["wind_direction"].head()
# TIMESTAMP
# 2025-01-01 00:00:00              North
# 2025-01-01 00:01:00    North-Northeast
# 2025-01-01 00:02:00               East

# Short codes + 8 sectors
ds.add_wind_direction("WD_deg", as_code=True, direction_to_use=8)
# -> "N", "NE", "E", ...

# 4-quadrant label
ds.add_wind_quadrant("WD_deg", as_code=True, quadrant_to_use=4)
# -> "I", "II", "III", "IV"
```

Both methods return `self` for chaining, mutate `ds.df` in place by adding
a new column, and cover the full bearing range including wrap-around at
0°/360° (see [Bearing Normalisation](#bearing-normalisation)).

---

## Sector Tables (`WIND_DIRECTIONS_*`)

Reference: [QWeather Wind Direction Guide — Legacy Wind Direction](https://dev.qweather.com/en/docs/api/weather/wind-guide/#legacy-wind-direction).

The 16-way table matches the QWeather **Legacy Wind Direction** table
bin-for-bin. The 8-way and 4-way tables follow standard compass
convention (45° and 90° arcs, both centred on North at 0°). All three
tables use inclusive-lower / exclusive-upper bin semantics:

```python
if wd["min_degree"] <= normalised_bearing < wd["max_degree"]:
    return wd["direction"] or wd["code"]
```

### `WIND_DIRECTIONS_16` — matches QWeather Legacy exactly

| Code | Direction | Center (°) | Range (°) |
|---|---|---|---|
| N | North | 0 | 348.75 – 11.25 |
| NNE | North-Northeast | 22.5 | 11.25 – 33.75 |
| NE | Northeast | 45 | 33.75 – 56.25 |
| ENE | East-Northeast | 67.5 | 56.25 – 78.75 |
| E | East | 90 | 78.75 – 101.25 |
| ESE | East-Southeast | 112.5 | 101.25 – 123.75 |
| SE | Southeast | 135 | 123.75 – 146.25 |
| SSE | South-Southeast | 157.5 | 146.25 – 168.75 |
| S | South | 180 | 168.75 – 191.25 |
| SSW | South-Southwest | 202.5 | 191.25 – 213.75 |
| SW | Southwest | 225 | 213.75 – 236.25 |
| WSW | West-Southwest | 247.5 | 236.25 – 258.75 |
| W | West | 270 | 258.75 – 281.25 |
| WNW | West-Northwest | 292.5 | 281.25 – 303.75 |
| NW | Northwest | 315 | 303.75 – 326.25 |
| NNW | North-Northwest | 337.5 | 326.25 – 348.75 |

### `WIND_DIRECTIONS_8` — 45° arcs

| Code | Direction | Center (°) | Range (°) |
|---|---|---|---|
| N | North | 0 | 337.5 – 22.5 |
| NE | Northeast | 45 | 22.5 – 67.5 |
| E | East | 90 | 67.5 – 112.5 |
| SE | Southeast | 135 | 112.5 – 157.5 |
| S | South | 180 | 157.5 – 202.5 |
| SW | Southwest | 225 | 202.5 – 247.5 |
| W | West | 270 | 247.5 – 292.5 |
| NW | Northwest | 315 | 292.5 – 337.5 |

### `WIND_DIRECTIONS_4` — 90° arcs (cardinal only)

| Code | Direction | Center (°) | Range (°) |
|---|---|---|---|
| N | North | 0 | 315 – 45 |
| E | East | 90 | 45 – 135 |
| S | South | 180 | 135 – 225 |
| W | West | 270 | 225 – 315 |

### Why "North" appears twice in each table

Every sector table stores the North row **twice**:

```python
# WIND_DIRECTIONS_4 excerpt
{"direction": "North", "code": "N", "degree": 0, "min_degree": 315, "max_degree": 360, ...},
{"direction": "North", "code": "N", "degree": 0, "min_degree": 0,   "max_degree": 45,  ...},
```

These are **not duplicates.** North physically wraps across the 0°/360°
boundary, but the lookup normalises bearings to `[0, 360)` via `% 360`
and then scans bins with `min <= x < max`. A single "315 – 45" bin can't
be expressed in `[0, 360)`, so North is represented as two half-bins.

Delete either half and every bearing in that half raises
`ValidationError` — see [Bearing Normalisation](#bearing-normalisation)
below.

---

## Quadrant Tables (`WIND_QUADRANTS_*`)

Quadrant tables use Roman-numeral codes and **do not wrap** North —
`Quadrant I` starts cleanly at 0°.

### `WIND_QUADRANTS_4` — 90° quadrants starting at 0°

| Code | Name | Center (°) | Range (°) |
|---|---|---|---|
| I | Quadrant I | 45 | 0 – 90 |
| II | Quadrant II | 135 | 90 – 180 |
| III | Quadrant III | 225 | 180 – 270 |
| IV | Quadrant IV | 315 | 270 – 360 |

### `WIND_QUADRANTS_8` — 45° quadrants starting at 0°

| Code | Name | Center (°) | Range (°) |
|---|---|---|---|
| I | Quadrant I | 22.5 | 0 – 45 |
| II | Quadrant II | 67.5 | 45 – 90 |
| III | Quadrant III | 112.5 | 90 – 135 |
| IV | Quadrant IV | 157.5 | 135 – 180 |
| V | Quadrant V | 202.5 | 180 – 225 |
| VI | Quadrant VI | 247.5 | 225 – 270 |
| VII | Quadrant VII | 292.5 | 270 – 315 |
| VIII | Quadrant VIII | 337.5 | 315 – 360 |

`WIND_QUADRANTS_8` is the default when `wind_quadrants=None` is passed
to `convert_to_wind_quadrant`.

---

## `MultiGasData` Methods

Signatures documented in full in
[API Reference → `MultiGasData`](API-Reference.md#multigasdata); a
condensed contract follows.

### `add_wind_direction`

```python
MultiGasData.add_wind_direction(
    wind_direction_column_name: str,
    as_code: bool = False,
    direction_to_use: Literal[16, 8, 4] = 16,
) -> Self
```

Reads bearings (in degrees) from `wind_direction_column_name` and writes
a new `wind_direction` column with the sector label — full name
(`"North"`, `"Northeast"`, …) by default, short code (`"N"`, `"NE"`, …)
when `as_code=True`. Picks the sector table by `direction_to_use`.

### `add_wind_quadrant`

```python
MultiGasData.add_wind_quadrant(
    wind_direction_column_name: str,
    as_code: bool = False,
    quadrant_to_use: Literal[8, 4] = 8,
) -> Self
```

Same shape as `add_wind_direction`, writes a `wind_quadrant` column and
picks the quadrant table by `quadrant_to_use`.

---

## Underlying Converters

Both `add_*` methods delegate to a scalar helper in
`multigas.utils.dataframe`. Call them directly when you need to map a
single bearing without a DataFrame in scope:

```python
from multigas.core.constant import WIND_DIRECTIONS_16, WIND_QUADRANTS_4
from multigas.utils.dataframe import (
    convert_to_wind_direction,
    convert_to_wind_quadrant,
)

convert_to_wind_direction(90.0, WIND_DIRECTIONS_16, as_code=True)  # -> "E"
convert_to_wind_quadrant(200.0, WIND_QUADRANTS_4)                  # -> "Quadrant III"
```

Both helpers:

- Return `None` for `NaN` input (preserves row alignment when mapping
  over a Series with gaps).
- Normalise every finite input with `% 360` before the bin scan.
- Raise `ValidationError` (auto-logged) if a finite, normalised bearing
  matches no bin — a bin-definition bug in the caller-supplied table.

---

## Bearing Normalisation

Before any bin lookup, bearings are normalised modulo 360:

```python
normalised = direction_degree % 360   # always in [0, 360)
```

| Input | Normalised | Notes |
|---|---|---|
| `0.0` | `0.0` | North (matches the 0–x half of the wrap pair) |
| `360.0` | `0.0` | Same as above; a single bin `[315, 360)` would miss it |
| `720.0` | `0.0` | Extra revolutions wrap cleanly |
| `-10.0` | `350.0` | Negative bearings wrap correctly |
| `45.0` | `45.0` | Boundary → higher bin (min-inclusive rule) |
| `NaN` | — | Returns `None`; no bin scan |

The exclusive upper bound (`min <= x < max`) on every bin plus the two
North halves is what makes `360.0` map to North instead of raising.

---

## Sources & References

- **QWeather Wind Direction Guide** — canonical for the 16-sector table:
  <https://dev.qweather.com/en/docs/api/weather/wind-guide/>
- **Legacy Wind Direction (Web API v7)** table specifically —
  <https://dev.qweather.com/en/docs/api/weather/wind-guide/#legacy-wind-direction>
  — this is the exact table `WIND_DIRECTIONS_16` mirrors.

The 4- and 8-sector tables are not defined by QWeather; they follow
standard meteorological compass convention (arcs of 90° and 45°
respectively, both centred on North at 0°). The quadrant tables
(`WIND_QUADRANTS_*`) are project-specific naming for evenly-spaced
Roman-numeral quadrants.
