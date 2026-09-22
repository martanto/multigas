# Data Columns

Reference for the column names that appear in a Campbell Scientific
multi-GAS TOA5 / CSV file loaded through `multigas`. Each row defines
one column as recorded by the datalogger — what the value represents,
its unit where applicable, and any onboard processing applied before
the value is written to the file.

> Back to [Home](Home.md) · Related:
> [Getting Started](Getting-Started.md),
> [API Reference](API-Reference.md),
> [Wind Analysis](Wind-Analysis.md).

Values are averaged over a **sample cycle** (a single datalogger
observation period). The column names below are the ones the datalogger
program emits; if you renamed columns downstream, look them up here by
the datalogger name they came from.

---

## Quick Reference

| Group | Columns |
|---|---|
| [System / metadata](#system--metadata) | `TIMESTAMP`, `RECORD`, `Site_Name`, `Duty_Cycle`, `Status_Flag` |
| [Power & instrument temperature](#power--instrument-temperature) | `Avg_batt_volt`, `Avg_regulated_volt`, `Avg_PTemp` |
| [Meteorological sensors](#meteorological-sensors) | `Avg_AirT`, `Avg_AirRH`, `Avg_FumaroleT`, `Avg_SampleP`, `Avg_AirP`, `Avg_Wind_Speed`, `Avg_Wind_Direction` |
| [Gas concentrations](#gas-concentrations) | `H2O`, `Avg_CO2_lowpass`, `Avg_SO2`, `Avg_H2S` |
| [H2O / CO2 ratios](#h2o--co2-ratios) | `Avg_H2O_CO2_ratio`, `Avg_H2O_CO2_intercept`, `#_valid_H2O_CO2_ratios` |
| [CO2 / SO2 ratios](#co2--so2-ratios) | `Avg_CO2_SO2_ratio`, `Avg_CO2_SO2_intercept`, `#_valid_CO2_SO2_ratios` |
| [H2S / SO2 ratios](#h2s--so2-ratios) | `Avg_H2S_SO2_ratio`, `Avg_H2S_SO2_intercept`, `#_valid_H2S_SO2_ratios` |
| [CO2 / S_tot ratios](#co2--s_tot-ratios) | `Avg_CO2_S_tot_ratio`, `Avg_CO2_S_tot_intercept`, `#_valid_CO2_S_tot_ratios` |
| [Sulfur proportions](#sulfur-proportions) | `Avg_SO2_proportion`, `Avg_H2S_proportion` |

---

## System / metadata

| Column | Definition |
|---|---|
| `TIMESTAMP` | Timestamp from the datalogger's internal clock. This is the source column `multigas` converts into the `pd.DatetimeIndex` on every loaded frame. |
| `RECORD` | Unique row number assigned by the datalogger to each observation in a data table. |
| `Site_Name` | Name of the multi-GAS instrument and / or its deployment location. |
| `Duty_Cycle` | Number of hours between sample cycles, expressed as a number. |
| `Status_Flag` | Numerical indicator of the operational state of the multi-GAS station. See [`SensorStatus`](API-Reference.md#sensorstatus) for the enum that names each code (e.g. `-1` = warming up, `1` = sample acquisition, `4` = span CO2 / SO2). |

---

## Power & instrument temperature

| Column | Definition |
|---|---|
| `Avg_batt_volt` | Average voltage of the multi-GAS power source during the sample cycle. **Not** compensated for diode drops, which can exceed 1 V depending on the power-system design. |
| `Avg_regulated_volt` | Average voltage during the sample cycle of the regulated power source that powers the multi-GAS electronics. |
| `Avg_PTemp` | Average temperature during the sample cycle measured by a thermistor inside the datalogger enclosure (**not** ambient air). |

---

## Meteorological sensors

| Column | Definition | Unit |
|---|---|---|
| `Avg_AirT` | Average ambient air temperature during the sample cycle. | °C |
| `Avg_AirRH` | Average relative humidity of ambient air during the sample cycle. | % |
| `Avg_FumaroleT` | Average temperature recorded by a K-type thermocouple during the sample cycle. Commonly used to track a volcanic gas vent or fumarole temperature. | °C |
| `Avg_SampleP` | Average pressure in the instrument's sample line during the sample cycle. | hPa |
| `Avg_AirP` | Ambient air pressure. | hPa |
| `Avg_Wind_Speed` | Average two-dimensional horizontal wind speed during the sample cycle. | m/s |
| `Avg_Wind_Direction` | Average two-dimensional horizontal wind direction (bearing) during the sample cycle. This is the column typically passed to `MultiGasData.add_wind_direction` / `add_wind_quadrant` — see [Wind Analysis](Wind-Analysis.md). | degrees |

---

## Gas concentrations

All gas concentrations are **average molar mixing ratios by volume**,
computed over the sample cycle. Units are as reported by the datalogger
program (typically ppm for CO2 / SO2 / H2S and mol% for H2O — confirm
against the source-file units row).

| Column | Definition |
|---|---|
| `H2O` | Average molar mixing ratio by volume of water vapour during the sample cycle. |
| `Avg_CO2_lowpass` | Average molar mixing ratio by volume of carbon dioxide (CO2) during the sample cycle. Onboard processing applies a single-pole recursive lowpass filter to raw CO2 collected at 1 Hz so the CO2 sensor's response matches the electrochemical sulfur sensors. The filter takes the form `CO2_lowpass = CO2_n * a + CO2_{n-1} * b`, where coefficients `a` and `b` sum to 1 and are derived empirically from step-response data during sensor calibrations. |
| `Avg_SO2` | Average molar mixing ratio by volume of sulfur dioxide (SO2) during the sample cycle. A pressure correction (`pcorr`) and linear span / offset are applied to the raw sensor value: `SO2 = SO2_pcorr * SPAN + OFFSET`. The appropriate pressure correction is determined by testing. |
| `Avg_H2S` | Average molar mixing ratio by volume of hydrogen sulfide (H2S) during the sample cycle. **H2S is not corrected for cross-sensitivity to SO2.** A pressure correction (`pcorr`) and linear span / offset are applied to the raw sensor value: `H2S = H2S_pcorr * SPAN + OFFSET`. The appropriate pressure correction is determined by testing. |

---

## Gas-ratio columns (shared contract)

The four ratio families below all share the same measurement recipe.
The datalogger runs an automated onboard linear regression over each
sample cycle using a **sliding 3-minute window**, and — once every
second — it decides whether the current window's fit is good enough to
report a ratio. A ratio is **valid** when all of these are true:

- coefficient of determination `r² > 0.7`,
- regression slope is positive (`slope > 0`),
- both target gases exceed a minimum quantity threshold.

Valid ratios are averaged over the sample cycle into `Avg_*_ratio`,
their y-intercepts are averaged into `Avg_*_intercept`, and the count
of valid ratios in the cycle is recorded in the corresponding
`#_valid_*_ratios` column. For 1 Hz data over a 30-minute sample
period, up to **1800** valid ratios are possible per cycle.

Every H2S-based ratio inherits the caveat from `Avg_H2S`: **H2S is not
corrected for cross-sensitivity to SO2**, so ratios that involve H2S
(directly or through `S_tot`) may be biased.

### H2O / CO2 ratios

| Column | Definition |
|---|---|
| `Avg_H2O_CO2_ratio` | Average molar H2O / CO2 ratio during the sample cycle from the automated onboard linear regression. |
| `Avg_H2O_CO2_intercept` | Average y-intercept from the same linear regression. |
| `#_valid_H2O_CO2_ratios` | Number of valid ratios (per the [shared contract](#gas-ratio-columns-shared-contract)) calculated in this sample cycle. |

### CO2 / SO2 ratios

| Column | Definition |
|---|---|
| `Avg_CO2_SO2_ratio` | Average molar CO2 / SO2 ratio during the sample cycle. |
| `Avg_CO2_SO2_intercept` | Average y-intercept from the same linear regression. |
| `#_valid_CO2_SO2_ratios` | Number of valid ratios calculated in this sample cycle. |

### H2S / SO2 ratios

| Column | Definition |
|---|---|
| `Avg_H2S_SO2_ratio` | Average molar H2S / SO2 ratio during the sample cycle. **H2S is not corrected for cross-sensitivity to SO2.** |
| `Avg_H2S_SO2_intercept` | Average y-intercept from the same linear regression. **H2S is not corrected for cross-sensitivity to SO2.** |
| `#_valid_H2S_SO2_ratios` | Number of valid ratios calculated in this sample cycle. **H2S is not corrected for cross-sensitivity to SO2.** |

### CO2 / S_tot ratios

`S_tot` ("S total") is `SO2 + H2S`. Because `H2S` is uncorrected for
SO2 cross-sensitivity, `S_tot` inherits that caveat.

| Column | Definition |
|---|---|
| `Avg_CO2_S_tot_ratio` | Average molar CO2 / S_tot ratio during the sample cycle. |
| `Avg_CO2_S_tot_intercept` | Average y-intercept from the same linear regression. |
| `#_valid_CO2_S_tot_ratios` | Number of valid ratios calculated in this sample cycle. |

---

## Sulfur proportions

Both proportions are derived from the H2S / SO2 ratio and inherit its
uncorrected-H2S caveat. Values are expressed as **percentages**.

| Column | Definition |
|---|---|
| `Avg_SO2_proportion` | Average proportion of SO2 to total sulfur (`SO2 / (SO2 + H2S)`) during the sample cycle. May be inaccurate — H2S is not corrected for cross-sensitivity to SO2. |
| `Avg_H2S_proportion` | Average proportion of H2S to total sulfur (`H2S / (SO2 + H2S)`) during the sample cycle. Same accuracy caveat as `Avg_SO2_proportion`. |

---

## Notes on units and pressure corrections

- Gas mixing ratios (`H2O`, `Avg_CO2_lowpass`, `Avg_SO2`, `Avg_H2S`)
  are volume-based (molar) mixing ratios; the exact unit (ppm, ppb,
  mol%) is set by the datalogger program and appears in the TOA5
  **units** row that `_load_csv` skips over. Confirm against the source
  file if a unit-sensitive calculation is downstream.
- Pressure appears in **hectopascals (hPa)** for both `Avg_SampleP`
  and `Avg_AirP`. The `pcorr` inside the SO2 / H2S formulas is an
  internal instrument-specific correction — the value in the file is
  already post-correction.
- Temperature is in **degrees Celsius**. `Avg_PTemp` measures the
  datalogger enclosure; `Avg_AirT` is ambient; `Avg_FumaroleT` is a
  thermocouple probe (typically inserted into a vent).

---

## When a column is missing

- `Query.missing_columns` returns columns that contain any NaN / empty
  value.
- `Query.empty_columns` returns columns that are entirely NaN, zero,
  or empty.
- Use `check_columns_exist` from `multigas.utils.validation` if you
  need to assert presence — it raises `ColumnError` (auto-logged) with
  every missing column named in a single message. See
  [API Reference](API-Reference.md) for the full utility surface.
