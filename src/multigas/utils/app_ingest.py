"""Bounded CSV parsing and disk-backed, globally ordered normalization."""

import os
import csv
import json
from uuid import uuid4
from pathlib import Path
from itertools import islice

import pandas as pd

from multigas.utils.analysis import daily_manifest
from multigas.utils.app_store import utc_now
from multigas.utils.dataframe import to_datetime_index


def quote(column: str) -> str:
    """Quote a validated SQL identifier (values use parameters)."""
    return '"' + column.replace('"', '""') + '"'


def csv_header(path: Path) -> dict:
    """Inspect a text CSV/TOA5 header and a strictly preliminary sample."""
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file, strict=True)
        first = next(reader)
        toa5 = first[0] == "TOA5"
        columns = next(reader) if toa5 else first
        units = dict(zip(columns, next(reader), strict=True)) if toa5 else {}
        if toa5:
            next(reader)  # processing descriptor
        if (
            not columns
            or len(columns) > 200
            or any(not c or len(c) > 150 for c in columns)
        ):
            raise ValueError("Use 1–200 named columns, each at most 150 characters")
        if len({c.lower() for c in columns}) != len(columns):
            raise ValueError("Duplicate column names are not supported")
        if any(c.startswith("__mg_") for c in columns):
            raise ValueError("Column names beginning __mg_ are reserved")
        sample = list(islice(reader, 12))
        if any(len(row) != len(columns) for row in sample):
            raise ValueError("CSV row width differs from the header")
        return {
            "format": "TOA5" if toa5 else "CSV",
            "columns": columns,
            "units": units,
            "sample": sample,
            "station": first[1] if toa5 and len(first) > 1 else "",
            "timestamp": "TIMESTAMP" if "TIMESTAMP" in columns else columns[0],
            "preliminary": True,
        }


def database(path: Path | str = ":memory:", temp_dir: Path | None = None):
    """Open bounded DuckDB; spill larger global operations to disk."""
    import duckdb

    connection = duckdb.connect(str(path))
    connection.execute(
        "SET memory_limit=?", [os.getenv("MULTIGAS_DUCKDB_MEMORY_LIMIT") or "512MB"]
    )
    connection.execute("SET threads=2")
    connection.execute("SET TimeZone='UTC'")
    if temp_dir is None and str(path) != ":memory:":
        temp_dir = Path(path).parent / "spill"
    if temp_dir is not None:
        connection.execute("SET temp_directory=?", [str(temp_dir)])
    return connection


def ingest(
    store, staged: dict, spec: dict, job: str, work: Path, batch_size: int = 50000
) -> dict:
    """Validate all rows, normalize globally, and atomically publish UTC partitions.

    Args:
        store (AppStore): Persistent local store.
        staged (dict): Validated staged-file metadata.
        spec (dict): Confirmed timestamp, mode, units, and normalization settings.
        job (str): Job identifier for cancellation and progress.
        work (Path): Disposable job directory.
        batch_size (int): Maximum rows in each pandas parsing batch.

    Returns:
        dict: Published dataset identifier.

    Raises:
        ValueError: If any row or timestamp is invalid.

    Example:
        >>> result = ingest(store, staged, spec, job, work)
    """
    path = store.root / "staged" / staged["id"]
    preview = csv_header(path)
    if preview != staged["preview"]:
        raise ValueError("Staged header changed; preview and upload again")
    columns = preview["columns"]
    timestamp = spec["timestamp"]
    if timestamp not in columns:
        raise ValueError("Select an available timestamp column")
    if set(spec["units"]) - set(columns):
        raise ValueError("Units contain unknown columns")
    values = [c for c in columns if c != timestamp]
    identifier = uuid4().hex
    output = work / "partitions"
    output.mkdir()
    connection = database(work / "ingest.duckdb")
    numeric = dict.fromkeys(values, True)
    total = 0
    missing_record = 0
    try:
        declarations = ",".join(f"{quote(c)} VARCHAR" for c in values)
        connection.execute(
            f"CREATE TABLE raw (__mg_time TIMESTAMPTZ, __mg_seq BIGINT{',' if declarations else ''}{declarations})"
        )
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.reader(file, strict=True)
            for _ in range(4 if preview["format"] == "TOA5" else 1):
                next(reader)
            while True:
                store.check(job)
                rows = list(islice(reader, batch_size))
                if not rows:
                    break
                if any(len(row) != len(columns) for row in rows):
                    raise ValueError(
                        f"Malformed CSV after record {total}; every row must match the header"
                    )
                frame = pd.DataFrame(rows, columns=columns)
                # Canonical ingest boundary handles aware/naive values and sorting.
                frame["__mg_seq"] = range(total, total + len(rows))
                frame = to_datetime_index(frame, timestamp, utc=True)
                if pd.DatetimeIndex(frame.index).hasnans:
                    raise ValueError(f"Missing timestamps after record {total}")
                total += len(rows)
                if spec["normalize"]:
                    frame = frame.replace(["NAN", "NaN", ""], None)
                    if "RECORD" in frame:
                        missing_record += int(frame["RECORD"].isna().sum())
                        frame = frame.dropna(subset=["RECORD"])
                        record = pd.to_numeric(frame["RECORD"], errors="raise")
                        if ((record % 1) != 0).any():
                            raise ValueError("RECORD must contain integers")
                for column in values:
                    candidate = frame[column].replace(["NAN", "NaN", ""], None)
                    converted = pd.to_numeric(candidate, errors="coerce")
                    numeric[column] &= int(converted.notna().sum()) == int(
                        candidate.notna().sum()
                    )
                frame["__mg_time"] = frame.index
                connection.register("batch", frame)
                fields = ["__mg_time", "__mg_seq", *values]
                connection.execute(
                    f"INSERT INTO raw SELECT {','.join(map(quote, fields))} FROM batch"
                )
                connection.unregister("batch")
                store.progress(
                    job,
                    min(0.65, total / max(total + batch_size, 1) * 0.65),
                    f"Validated {total:,} records",
                )
        if total == 0:
            raise ValueError("The upload contains no observations")
        store.progress(job, 0.7, "Resolving duplicate timestamps globally")
        select = ["__mg_time", "__mg_seq"] + [
            f"TRY_CAST({quote(c)} AS DOUBLE) AS {quote(c)}"
            if numeric[c] and spec["normalize"]
            else quote(c)
            for c in values
        ]
        dedupe = (
            "QUALIFY row_number() OVER (PARTITION BY __mg_time ORDER BY __mg_seq DESC)=1"
            if spec["normalize"]
            else ""
        )
        connection.execute(
            f"CREATE TABLE unique_rows AS SELECT {','.join(select)} FROM raw {dedupe}"
        )
        unique_count = connection.execute(
            "SELECT count(*) FROM unique_rows"
        ).fetchone()[0]
        interval = {"1s": 1, "2s": 2, "1min": 60, "6h": 21600}.get(spec["mode"])
        where = ""
        if spec["normalize"] and interval:
            where = f"WHERE __mg_previous IS NULL OR epoch(__mg_time)-epoch(__mg_previous)={interval}"
        connection.execute(
            f"CREATE TABLE normalized AS SELECT * EXCLUDE (__mg_seq,__mg_previous) FROM (SELECT *,lag(__mg_time) OVER (ORDER BY __mg_time,__mg_seq) AS __mg_previous FROM unique_rows) {where}"
        )
        store.check(job)
        counts = dict(
            connection.execute(
                "SELECT strftime(__mg_time,'%Y-%m-%d'), count(*) FROM normalized GROUP BY 1 ORDER BY 1"
            ).fetchall()
        )
        if not counts:
            raise ValueError("Normalization left no usable observations")
        for index, day in enumerate(counts):
            store.check(job)
            # Output path is generated, not supplied by a request.
            target = output / f"{day}.parquet"
            connection.execute(
                "COPY (SELECT * FROM normalized WHERE CAST(__mg_time AS DATE)=CAST(? AS DATE) ORDER BY __mg_time) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
                [day, str(target)],
            )
            store.progress(
                job, 0.8 + 0.18 * index / len(counts), f"Writing UTC day {day}"
            )
        retained = sum(counts.values())
        metadata = {
            "id": identifier,
            "version": identifier,
            "station": spec["station"].strip(),
            "source": staged["name"],
            "checksum": staged["checksum"],
            "created": utc_now(),
            "mode": spec["mode"],
            "units": {**preview["units"], **spec["units"]},
            "columns": values,
            "numeric_columns": [c for c in values if numeric[c]],
            "records": retained,
            "manifest": daily_manifest(counts, spec["mode"]),
            "normalization": {
                "enabled": spec["normalize"],
                "input": total,
                "missing_record": missing_record,
                "duplicates": total - missing_record - unique_count,
                "sampling_excluded": unique_count - retained,
                "retained": retained,
                "first_row_retained": True,
                "naive_timezone": "UTC",
                "duplicate_policy": "last source row wins"
                if spec["normalize"]
                else "preserve source rows",
            },
        }
        (output / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        import shutil

        shutil.copyfile(path, output / "original.csv")
        # Publication and job completion cannot race with a cancellation request.
        with store.lock:
            store.check(job)
            output.replace(store.root / "datasets" / identifier)
            store.put("datasets", metadata)
        return {"dataset": identifier}
    finally:
        connection.close()
