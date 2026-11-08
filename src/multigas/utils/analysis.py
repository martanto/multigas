"""Shared scientific panel definitions, unit conversions, and daily summaries."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from multigas.core.types import DatasetType
from multigas.core.exceptions import ValidationError


@dataclass(frozen=True)
class Panel:
    """One summary panel, shared by scientific exports and the dashboard."""

    id: str
    label: str
    columns: tuple[str, ...]
    colors: tuple[str, ...]
    unit: str = "ratio"


PANELS = (
    Panel("co2_stot", "CO₂/Sₜₒₜ", ("Avg_CO2_S_tot_ratio",), ("#326985",)),
    Panel("h2s_so2", "H₂S/SO₂", ("Avg_H2S_SO2_ratio",), ("#a15b30",)),
    Panel("co2_h2s", "CO₂/H₂S", ("Avg_CO2_H2S_ratio",), ("#6b5793",)),
    Panel("co2_so2", "CO₂/SO₂", ("Avg_CO2_SO2_ratio",), ("#376f61",)),
    Panel("h2o_co2", "H₂O/CO₂", ("Avg_H2O_CO2_ratio",), ("#8e6c27",)),
    Panel("co2", "CO₂", ("Avg_CO2_lowpass",), ("#326985",), "source"),
    Panel("so2", "SO₂", ("Avg_SO2",), ("#b36a26",), "source"),
    Panel("h2s", "H₂S", ("Avg_H2S",), ("#775b98",), "source"),
    Panel("h2o", "H₂O", ("H2O",), ("#397c89",), "source"),
    Panel(
        "proportions",
        "Sulfur proportions",
        ("Avg_SO2_proportion", "Avg_H2S_proportion"),
        ("#b36a26", "#775b98"),
        "%",
    ),
)
PANEL_MAP = {panel.id: panel for panel in PANELS}
COLUMN_ALIASES = {
    "Avg_CO2_lowpass": ("CO2_lowpass", "CO2"),
    "Avg_SO2": ("SO2",),
    "Avg_H2S": ("H2S",),
    "Avg_CO2_S_tot_ratio": ("CO2/S_total_ratio_3min",),
    "Avg_H2S_SO2_ratio": ("H2S/SO2_ratio_3min",),
    "Avg_CO2_H2S_ratio": ("CO2/H2S_ratio_3min", "calculated_CO2_H2S"),
    "Avg_CO2_SO2_ratio": ("CO2/SO2_ratio_3min",),
    "Avg_H2O_CO2_ratio": ("H2O/CO2_ratio_3min",),
    "Avg_SO2_proportion": ("SO2/S_total_3min",),
    "Avg_H2S_proportion": ("H2S/S_total_3min",),
}
FORMULAS = {
    "co2_stot": ("Avg_CO2_lowpass", ("Avg_SO2", "Avg_H2S")),
    "h2s_so2": ("Avg_H2S", ("Avg_SO2",)),
    "co2_h2s": ("Avg_CO2_lowpass", ("Avg_H2S",)),
    "co2_so2": ("Avg_CO2_lowpass", ("Avg_SO2",)),
    "h2o_co2": ("H2O", ("Avg_CO2_lowpass",)),
}
UNIT_FACTORS = {
    "ppm": 1.0,
    "ppmv": 1.0,
    "ppb": 0.001,
    "%": 10000.0,
    "percent": 10000.0,
    "fraction": 1000000.0,
}
CAVEAT = "H₂S is uncorrected for SO₂ cross-sensitivity; H₂S ratios and sulfur proportions inherit this limitation."


def panel_metadata() -> list[dict]:
    """Return JSON-compatible shared panel definitions."""
    return [asdict(panel) for panel in PANELS]


def prepare_panels(
    df: pd.DataFrame,
    units: dict[str, str] | None = None,
    ratio_source: str = "onboard",
    panels: list[str] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Resolve panels without guessing units or silently replacing onboard ratios.

    Args:
        df (pd.DataFrame): Time-indexed concentrations and onboard channels.
        units (dict): Confirmed source units, keyed by column.
        ratio_source (str): ``onboard`` or ``calculated``.
        panels (list[str] | None): Requested panel identifiers.

    Returns:
        tuple[pd.DataFrame, dict]: Resolved series and per-column provenance.

    Raises:
        ValidationError: If an explicitly requested calculation has unknown units.

    Example:
        >>> resolved, provenance = prepare_panels(df, {"Avg_SO2": "ppm"})
    """
    units = units or {}
    result = df.copy()
    units = dict(units)
    for canonical, aliases in COLUMN_ALIASES.items():
        source = next((c for c in aliases if c in result), None)
        if canonical not in result and source:
            result[canonical] = result[source]
            if source in units:
                units[canonical] = units[source]
    provenance = {}
    if ratio_source not in {"onboard", "calculated"}:
        raise ValidationError("Ratio source must be onboard or calculated")
    for panel_id in panels or list(PANEL_MAP):
        if panel_id not in PANEL_MAP:
            raise ValidationError(f"Unknown panel: {panel_id}")
        panel = PANEL_MAP[panel_id]
        calculate = ratio_source == "calculated" and (
            panel_id in FORMULAS or panel_id == "proportions"
        )
        # CO2/H2S has no onboard channel: a calculated alternative is explicit.
        if calculate:
            if panel_id == "proportions":
                required = ["Avg_SO2", "Avg_H2S"]
            else:
                numerator, denominators = FORMULAS[panel_id]
                required = [numerator, *denominators]
            if any(column not in df for column in required):
                continue
            if any(units.get(c, "").lower() not in UNIT_FACTORS for c in required):
                raise ValidationError(
                    f"Confirm compatible concentration units for {', '.join(required)}"
                )
            values = {
                c: pd.to_numeric(df[c], errors="coerce")
                * UNIT_FACTORS[units[c].lower()]
                for c in required
            }
            if panel_id == "proportions":
                denominator = values["Avg_SO2"] + values["Avg_H2S"]
                for column, gas in zip(panel.columns, required, strict=True):
                    result[column] = (100 * values[gas] / denominator).where(
                        denominator > 0
                    )
                    provenance[column] = {
                        "source": "calculated",
                        "formula": f"100 * {gas} / (SO2 + H2S)",
                        "unit": "%",
                    }
            else:
                denominator = sum(values[c] for c in denominators)
                column = panel.columns[0]
                result[column] = (values[numerator] / denominator).where(
                    denominator > 0
                )
                provenance[column] = {
                    "source": "calculated",
                    "formula": f"{numerator} / ({' + '.join(denominators)})",
                    "unit": "mol/mol",
                }
        else:
            for column in panel.columns:
                if column not in result:
                    continue
                unit = units.get(
                    column, "mol/mol" if panel.unit == "ratio" else "unconfirmed"
                )
                provenance[column] = {"source": "onboard", "unit": unit}
                if panel_id == "proportions":
                    if unit == "fraction":
                        result[column] = (
                            pd.to_numeric(result[column], errors="coerce") * 100
                        )
                        provenance[column].update(unit="%", conversion="fraction × 100")
                    elif unit not in {"%", "percent"}:
                        result = result.drop(columns=[column])
        for column in panel.columns:
            if column in result:
                result[column] = pd.to_numeric(result[column], errors="coerce").replace(
                    [np.inf, -np.inf], np.nan
                )
    return result, provenance


def daily_manifest(counts: dict[str, int], mode: str) -> list[dict]:
    """Include missing UTC dates and nullable completeness for categorical modes."""
    if not counts:
        return []
    try:
        expected = DatasetType(mode).total_data
    except ValueError:
        expected = None
    return [
        {
            "date": str(day.date()),
            "records": counts.get(str(day.date()), 0),
            "expected": expected,
            "completeness": min(100, counts.get(str(day.date()), 0) / expected * 100)
            if expected
            else None,
        }
        for day in pd.date_range(min(counts), max(counts), freq="D")
    ]
