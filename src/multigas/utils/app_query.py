"""Validated, immutable, disk-backed analysis queries and bounded series."""

import json
import shutil
from uuid import uuid4

import pandas as pd

from multigas.utils.analysis import (
    CAVEAT,
    FORMULAS,
    PANEL_MAP,
    UNIT_FACTORS,
    COLUMN_ALIASES,
    prepare_panels,
)
from multigas.utils.app_ingest import quote, database


def utc_value(value: str) -> str:
    """Parse a request timestamp, always returning an aware UTC value."""
    time = pd.Timestamp(value)
    if pd.isna(time):
        raise ValueError("Invalid date")
    return (
        time.tz_localize("UTC") if time.tz is None else time.tz_convert("UTC")
    ).isoformat()


class DatasetQuery:
    """Isolated connection over one immutable dataset and a complete analysis spec."""

    def __init__(self, store, spec):
        self.spec = spec
        self.metadata = store.get("datasets", spec.dataset)
        self.columns = self.metadata["columns"].copy()
        self.numeric = self.metadata["numeric_columns"].copy()
        self.temp_dir = store.root / "work" / uuid4().hex
        self.connection = database(temp_dir=self.temp_dir)
        self.provenance = {}
        self.params = []
        try:
            self.connection.read_parquet(
                str(store.root / "datasets" / self.metadata["id"] / "*.parquet")
            ).create_view("original")
            units = dict(self.metadata["units"])
            aliases = []
            for canonical, alternatives in COLUMN_ALIASES.items():
                source = next((c for c in alternatives if c in self.columns), None)
                if canonical not in self.columns and source:
                    aliases.append(f"{quote(source)} AS {quote(canonical)}")
                    self.columns.append(canonical)
                    if source in self.numeric:
                        self.numeric.append(canonical)
                    if source in units:
                        units[canonical] = units[source]
            self.metadata["units"] = units
            self.connection.execute(
                "CREATE VIEW source AS SELECT *"
                + ("," + ",".join(aliases) if aliases else "")
                + " FROM original"
            )
            selected = spec.panels or list(PANEL_MAP)
            if any(p not in PANEL_MAP for p in selected):
                raise ValueError("Unknown panel")
            dummy = pd.DataFrame({c: [1.0] for c in self.columns})
            _, self.provenance = prepare_panels(
                dummy, units, spec.ratio_source, selected
            )
            replacements = {}
            for panel_id in selected:
                panel = PANEL_MAP[panel_id]
                if spec.ratio_source == "calculated" and (
                    panel_id in FORMULAS or panel_id == "proportions"
                ):
                    if panel_id == "proportions":
                        required = ["Avg_SO2", "Avg_H2S"]
                    else:
                        numerator, denominators = FORMULAS[panel_id]
                        required = [numerator, *denominators]
                    if any(c not in self.columns for c in required):
                        continue
                    values = {
                        c: f"(TRY_CAST({quote(c)} AS DOUBLE)*{UNIT_FACTORS[units[c].lower()]})"
                        for c in required
                    }
                    denominator = "+".join(
                        values[c]
                        for c in (
                            required if panel_id == "proportions" else denominators
                        )
                    )
                    for index, column in enumerate(panel.columns):
                        num = (
                            values[required[index]] + "*100"
                            if panel_id == "proportions"
                            else values[numerator]
                        )
                        replacements[column] = (
                            f"CASE WHEN ({denominator})>0 THEN ({num})/({denominator}) ELSE NULL END"
                        )
                elif panel_id == "proportions":
                    for c in panel.columns:
                        if c in self.columns:
                            if units.get(c) == "fraction":
                                replacements[c] = f"TRY_CAST({quote(c)} AS DOUBLE)*100"
                            elif units.get(c) not in {"%", "percent"}:
                                replacements[c] = "NULL::DOUBLE"
            fields = ["__mg_time"] + [
                f"{replacements.get(c, quote(c))} AS {quote(c)}" for c in self.columns
            ]
            for column, expression in replacements.items():
                if column not in self.columns:
                    self.columns.append(column)
                    self.numeric.append(column)
                    fields.append(f"{expression} AS {quote(column)}")
            self.connection.execute(
                f"CREATE VIEW resolved AS SELECT {','.join(fields)} FROM source"
            )
            conditions = []
            if spec.start:
                conditions.append("__mg_time>=CAST(? AS TIMESTAMPTZ)")
                self.params.append(utc_value(spec.start))
            if spec.end:
                conditions.append("__mg_time<=CAST(? AS TIMESTAMPTZ)")
                self.params.append(utc_value(spec.end))
            if spec.start and spec.end and utc_value(spec.start) > utc_value(spec.end):
                raise ValueError("Start must precede end")
            for rule in spec.filters:
                if rule.column not in self.numeric:
                    raise ValueError(
                        f"Filter column unavailable or nonnumeric: {rule.column}"
                    )
                conditions.append(
                    f"TRY_CAST({quote(rule.column)} AS DOUBLE) {rule.comparator} ?"
                )
                self.params.append(rule.value)
            if set(spec.channels) - set(self.columns):
                raise ValueError("One or more selected channels are unavailable")
            self.sql = "SELECT * FROM resolved" + (
                " WHERE " + " AND ".join(conditions) if conditions else ""
            )
        except Exception:
            self.connection.close()
            raise

    def close(self):
        """Release the request's DuckDB connection."""
        self.connection.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def count(self) -> int:
        """Count full-resolution filtered samples."""
        return self.connection.execute(
            f"SELECT count(*) FROM ({self.sql})", self.params
        ).fetchall()[0][0]

    def statistics(self) -> dict:
        """Compute full-resolution finite channel statistics independently of coverage."""
        total = self.count()
        statistics = {}
        for c in self.spec.channels or self.numeric:
            value = f"TRY_CAST({quote(c)} AS DOUBLE)"
            count, low, high, mean = self.connection.execute(
                f"SELECT count(*) FILTER(WHERE isfinite({value})),min({value}) FILTER(WHERE isfinite({value})),max({value}) FILTER(WHERE isfinite({value})),avg({value}) FILTER(WHERE isfinite({value})) FROM ({self.sql})",
                self.params,
            ).fetchone()
            statistics[c] = {
                "valid": count,
                "validity": count / total * 100 if total else None,
                "min": low,
                "max": high,
                "mean": mean,
            }
        return {
            "filtered_records": total,
            "channels": statistics,
            "provenance": self.provenance,
            "caveat": CAVEAT,
        }

    def rows(self, offset: int, limit: int) -> list[dict]:
        """Return one bounded page with JSON-safe nonfinite values."""
        frame = self.connection.execute(
            f"{self.sql} ORDER BY __mg_time LIMIT ? OFFSET ?",
            [*self.params, limit, offset],
        ).df()
        frame = frame.rename(columns={"__mg_time": "TIMESTAMP"})
        return json.loads(frame.to_json(orient="records", date_format="iso"))

    def series(self, limit: int = 8000, offset: int = 0) -> list[dict]:
        """Return a bounded page of every source observation, without reduction."""
        if not 1 <= limit <= 8000 or offset < 0:
            raise ValueError("Use limit 1–8000 and a nonnegative offset")
        count = self.count()
        channels = self.spec.channels or [
            c
            for p in self.spec.panels or list(PANEL_MAP)
            for c in PANEL_MAP[p].columns
            if c in self.columns
        ]
        channels = list(dict.fromkeys(channels))
        fields = ["__mg_time"] + [
            f"CASE WHEN isfinite(TRY_CAST({quote(c)} AS DOUBLE)) THEN TRY_CAST({quote(c)} AS DOUBLE) ELSE NULL END AS {quote(c)}"
            for c in channels
        ]
        rows = self.connection.execute(
            f"SELECT {','.join(fields)} FROM ({self.sql}) ORDER BY __mg_time LIMIT ? OFFSET ?",
            [*self.params, limit, offset],
        ).fetchall()
        return [
            {
                "channel": c,
                "source_count": count,
                "rendered_count": len(rows),
                "points": [
                    {"timestamp": r[0].isoformat(), "value": r[i + 1]} for r in rows
                ],
            }
            for i, c in enumerate(channels)
        ]
